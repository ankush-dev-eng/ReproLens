# ReproLens System Architecture

> **Philosophy:** *"Don't trust the diagnosis. Trust the failing test."*

ReproLens is an autonomous GitHub issue reproduction engine designed to transform ambiguous, conversational bug reports into deterministic, minimal, sandboxed reproduction test cases with verified source-code citations.

---

## 1. High-Level System Architecture

ReproLens operates through a decoupled, multi-stage pipeline where each stage produces verifiable, auditable artifacts.

```
[ GitHub Issue / URL ]
         │
         ▼
 ┌───────────────────────┐
 │  Stage 1: Ingestion   │ ── Extracts title, body, tracebacks, mentioned symbols, versions
 └───────────────────────┘
         │
         ▼
 ┌───────────────────────┐
 │  Stage 2: AST Index   │ ── Parses Python AST, builds callgraphs, deterministic scoring
 └───────────────────────┘
         │
         ▼
 ┌───────────────────────┐
 │ Stage 3: Hypotheses   │ ── Formulates root-cause claims, verifies citations in worktree
 └───────────────────────┘
         │
         ▼
 ┌───────────────────────┐
 │ Stage 4: Synthesis    │ ── Synthesizes pytest test, enforces AST Static Security Guard
 └───────────────────────┘
         │
         ▼
 ┌───────────────────────┐
 │ Stage 5: Sandboxing   │ ── Executes in rootless container, multi-branch classification
 └───────────────────────┘
         │
         ├──────────────────────┬──────────────────────┐
         ▼                      ▼                      ▼
  [ REPRODUCED ]       [ NOT_REPRODUCED ]      [ INVALID_TEST ]
         │                      │                      │
         ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Automated Git   │   │  Honest Refusal  │   │  AST Diagnostic  │
│     Bisect       │   │   Audit Trail    │   │    Feedback      │
└──────────────────┘   └──────────────────┘   └──────────────────┘
         │
         ▼
┌──────────────────┐
│  4-Gate Patch    │ ── Baseline fail -> Clean apply -> Post-patch 3/3 pass -> 0 regressions
│   Validation     │
└──────────────────┘
```

---

## 2. Core Modules Breakdown

### 2.1 Ingestion Layer (`reprolens/github_client.py`)
- **Normalized Inputs**: Accepts full GitHub issue URLs (`https://github.com/owner/repo/issues/123`), short strings (`owner/repo#123`), or raw issue text.
- **Structural Extraction**: Automatically parses fenced code blocks, exception tracebacks (matching Python standard tracebacks and pytest `E   ...` lines), referenced symbols, and library version strings.
- **Resilience**: Implements exponential backoff on HTTP 403/429 rate limits, handles 404/410 errors gracefully, and detects pull request URLs to prevent triaging non-issues.

### 2.2 Repository & AST Engine (`reprolens/repo.py`, `indexer.py`, `retrieval.py`, `refs.py`)
- **Safe Cloner**: Clones target repositories with arbitrary git hooks disabled via an empty temp directory (`core.hooksPath`).
- **Revision Resolver**: Resolves the exact commit prior to issue opening using git history (`git rev-list -1 --before=...`) or accepts explicit commit SHAs.
- **Isolated Worktrees**: Creates ephemeral worktrees (`git worktree add --detach`) for every test execution attempt, preventing filesystem contamination.
- **Deterministic AST Retrieval**: Indexes class definitions, function signatures, docstrings, and import graphs using Python's standard `ast` library. Code retrieval prioritizes mentioned tracebacks and symbols using deterministic ranking without opaque vector databases or embeddings.
- **Source Citation Verifier (`refs.py`)**: Validates that LLM file:line citations point to real files within repository bounds, preventing directory traversal and detecting hallucinated citations.

### 2.3 LLM Reasoning Layer (`reprolens/llm/`)
- **Schema Enforcement**: All stages strictly enforce Pydantic v2 schemas (`IssueUnderstandingSchema`, `RootCauseInvestigationSchema`, `ReproTestGenerationSchema`, `TestRepairSchema`, `PatchGenerationSchema`).
- **Prompt Injection Defense**: All untrusted issue and repository content is segregated into explicit XML-style delimiters (`<<<UNTRUSTED_ISSUE_DATA>>>`, `<<<UNTRUSTED_REPOSITORY_SOURCE>>>`) with system prompts commanding the LLM to ignore embedded commands.
- **Resilient Client (`llm/client.py`)**: OpenRouter client with exponential backoff on 429 rate limits, automatic model fallback across configured reasoning models, schema re-prompting on validation error, and SQLite-backed response caching.

### 2.4 AST Test Guard & Multi-Branch Classifier (`reprolens/test_guard.py`, `classify.py`)
- **Static Security Guard**: AST-level security checker rejecting dangerous operations before any execution:
  - Forbids network/socket calls, `subprocess`, `os.system`, `eval`, `exec`, and `ctypes`.
  - Rejects unconditional failures (`assert False`, `pytest.fail()`, `pytest.skip`).
  - Requires module-level `EXPECTED_SYMPTOM` dictionary.
  - Rejects assertion weakening or deletion in repair attempts.
- **Multi-Branch Classifier**: Analyzes exit codes, stdout, and stderr:
  - `REPRODUCED`: Test failed with the exact expected exception type and matching message regex.
  - `NOT_REPRODUCED`: Test passed 3/3 consecutive times (honest refusal: bug does not manifest).
  - `INVALID_TEST`: Test raised an unexpected exception type (e.g. test syntax error or unrelated failure).
  - `ENVIRONMENT_ERROR`: Setup failure or container crash.
  - `EXECUTION_TIMEOUT`: Wall-clock execution exceeded timeout limits.

### 2.5 Evidence Ledger (`reprolens/ledger.py`)
- Maintains a verifiable, auditable chain of evidence:
  - **💡 AI Hypotheses**: Unverified probabilistic conjectures generated during analysis.
  - **📄 Source Code Citations**: Deterministically AST-verified line ranges and code snippets in the worktree.
  - **🧪 Execution Evidence**: Empirical container execution records with timestamps, durations, exit codes, and captured runner logs.
- Hypotheses are only promoted to verified claims when confirmed by failing test evidence.

### 2.6 Sandboxed Execution Layer (`reprolens/sandbox/`)
- **`DockerBackend`**: Rootless, unprivileged container execution (`--network none`, `--cap-drop=ALL`, `--user 10001:10001`, `--memory=512m`, `--cpus=1`, `--pids-limit=128`, read-only root filesystem, tmpfs `/tmp`, wall-clock timeout kill).
- **`DemoBackend`**: Fail-closed fallback backend for environments without Docker or Streamlit Community Cloud. Serves pre-recorded benchmark artifacts and refuses arbitrary code execution.
- **`RemoteRunnerBackend`**: Optional gRPC / REST adapter for dedicated remote sandbox runner clusters.

### 2.7 Automated Git Bisect Engine (`reprolens/bisect.py`)
- **Exponential Backward Search**: Walks backwards $2^0, 2^1, 2^2, \dots$ revisions from the buggy commit, running the minimal reproducer 3 times until a known-good commit is identified.
- **Binary Search**: Executes binary bisection between known-good and known-bad revisions in isolated worktrees.
- **Skip Handling**: Gracefully handles exit code 125 (unbuildable / broken syntax commits) by skipping to adjacent revisions.

### 2.8 4-Gate Patch Validation Engine (`reprolens/patching.py`)
1. **Gate 1 (Baseline Invariant)**: Reproducer test MUST fail on the unpatched revision.
2. **Gate 2 (Patch Application)**: Unified diff applies cleanly with `git apply --check` without rejected hunks.
3. **Gate 3 (Post-Patch Consistency)**: Reproducer test MUST pass 3/3 consecutive times after patch application.
4. **Gate 4 (Zero Regressions)**: Existing repository test suite produces 0 new failures.

---

## 3. Database Schema (`reprolens.db`)

All state is stored in SQLite using WAL mode:
- `investigations`: Investigation metadata, target repo, commit SHA, duration, and final status.
- `claims`: Hypotheses, source citations, and execution evidence records with verification flags.
- `source_refs`: Verified file paths, line ranges, and code snippets.
- `attempts`: Test source code, exit code, execution origin (live vs recorded), stdout, and stderr.
- `patches`: Unified diffs and 4-gate validation outcomes.
- `bisect_runs`: Bisection test steps (good, bad, skip, flaky) and pass/fail counts.
- `eval_runs`: Multi-case benchmark evaluation summaries and accuracy metrics.
- `llm_cache`: Prompt/response cache with SHA-256 keys.
- `llm_calls`: Token consumption and cost audit logs.
