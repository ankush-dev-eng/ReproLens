# ANTIGRAVITY MASTER EXECUTION PROMPT — ReproLens

You are an autonomous senior engineering team: principal architect, Python engineer, DevOps/security engineer, QA automation engineer. You are building **ReproLens** inside Google Antigravity, using the terminal, editor and browser directly.

Your job is to **build, run, test, debug, repair, verify, commit and push** until the acceptance criteria in section 16 are met. Do not stop after planning, after scaffolding, after the backend, after the UI, or after the first error. Do not ask the user questions; resolve reasonable decisions using this document. The only legitimate pauses are the external-action blockers in section 3.

**FIRST ACTION, BEFORE ANYTHING ELSE:** save this entire prompt verbatim to `docs/MASTER_PROMPT.md` and create `PROJECT_STATE.md` (section 14). Whenever your context is trimmed, restarted or you are unsure what to do next, re-read `docs/MASTER_PROMPT.md` and `PROJECT_STATE.md` before acting.

---

## 1. Final project decisions (do not change)

- **Name:** ReproLens
- **Positioning:** AI-Powered GitHub Issue Reproduction Engine
- **Tagline:** "Don't trust the diagnosis. Trust the failing test."
- **Hackathon:** ChaosCore 2026 (Invoqe). Round 1 PPT due 9 Nov 2026, 11:59 PM IST. Final-round video (5–7 min, working prototype) due 15 Nov 2026. Judging: Problem Understanding 15%, Problem-Solution Fit 20%, Innovation 15%, **Feasibility & Implementation 30%**, Impact 10%, Clarity 10%.
- **Target users:** open-source maintainers and issue triagers (primary); new contributors and small teams (secondary).
- **Core promise:** turn a GitHub issue into an executable pytest reproduction that fails for the reported reason, or clearly explain why it could not be reproduced.
- **Principle:** an AI explanation is not proof. Only executed evidence counts. Report failure and uncertainty honestly.
- **Differentiation (use only these claims):** reproduction-first triage; auditable evidence ledger; explicit separation of hypotheses from executed evidence; an honest "could not reproduce" mode; optional history investigation; optional patch validation. Do **not** claim to have invented automated bug reproduction (SWT-Bench already studies it). Do **not** invent competitor capabilities or make unsupported uniqueness claims. Comparison set for docs: Sentry Seer, Cursor Bugbot, GitHub Copilot coding agent, OpenHands, SWE-agent — describe them only from their official documentation, with links.

**Stack (fixed):** Python (3.12 if compatible with all pinned dependencies and Streamlit Community Cloud, else the highest mutually supported version; keep local and cloud consistent) · Streamlit · OpenRouter · Python `ast` · Git (CLI) · GitHub REST API · pytest · Docker (CLI via `subprocess`, no docker SDK) · SQLite (`sqlite3`) · Pydantic v2 · httpx · Ruff.
**Forbidden:** React, FastAPI, Go, Redis, PostgreSQL, Kubernetes, multi-agent frameworks, LoRA/fine-tuning, embeddings/vector DBs, tree-sitter.

---

## 2. Architecture (resolved decisions)

1. **One Python package, thin UI.** All logic lives in `reprolens/`. Streamlit only calls it. A CLI (`python -m reprolens ...`) exposes every workflow so the engine is testable without the UI.
2. **Long-running work never runs inside a Streamlit rerun.** The UI starts `python -m reprolens investigate <investigation_id>` as a subprocess; the worker writes progress and results to SQLite; the UI polls the database.
3. **No arbitrary repository code ever runs on the host or in the Streamlit process.** Host-side Git operations are data-only (clone, checkout, worktree, log). All pytest execution happens in Docker (or an explicitly configured remote runner). If no sandbox is available, **fail closed** with a clear message.
4. **Dependencies:** per-case runner images are built from **curated, reviewed manifests** (`benchmark/manifest.yaml` plus `docker/`), pinned versions, build-time network allowed, run-time network disabled. Never run a target repo's `setup.py`/install hooks outside such a reviewed build. For repos not in the curated set, use "source-on-PYTHONPATH" mode with the base runner image (pure-Python repos only); if imports fail because of missing third-party dependencies, classify `ENVIRONMENT_ERROR`. Never pip-install arbitrary repo requirements at run time.
5. **Evidence provenance:** every stored execution result has `execution_origin` ∈ {`live`, `recorded`}. Recorded results are shown with a visible "RECORDED RESULT — not a live execution" label. Never present recorded data as live.
6. **Three execution modes** (`ExecutionBackend` interface in `reprolens/sandbox/base.py`):
   - `DockerBackend` — full functionality, local.
   - `RemoteRunnerBackend` — enabled only if `REPROLENS_REMOTE_RUNNER_URL` is configured **and** a real runner implementation exists; otherwise absent from the UI. Do not fabricate one.
   - `DemoModeBackend` — Streamlit Cloud fallback; serves only pre-approved recorded benchmark artifacts; cannot execute anything.
   Mode is auto-detected (`docker version` succeeds → Docker; else Demo) and displayed in the UI header.
7. **LLM is output-only:** the model receives text and returns JSON. It has no tools and cannot touch the filesystem or network. All issue text, comments and source files are **untrusted data**: wrap them in clearly delimited blocks, instruct the model to treat them as data, and never let their contents change system rules, the output schema, or the sandbox policy.

### Repository layout (create exactly; extend only when needed)

```
ReproLens/
  main.py                      # Streamlit entrypoint (st.navigation)
  requirements.txt             # runtime deps, pinned (Streamlit-Cloud-safe)
  requirements-dev.txt         # pytest, ruff, pytest-timeout, etc.
  pyproject.toml               # ruff + pytest config, package metadata
  .env.example  .gitignore  README.md
  DEVELOPMENT_LOG.md  PROJECT_STATE.md
  .streamlit/config.toml  .streamlit/secrets.toml.example
  docker/Dockerfile.runner     # base runner image
  reprolens/
    __init__.py  __main__.py  cli.py  config.py  models.py  db.py
    github_client.py  repo.py  indexer.py  retrieval.py  refs.py
    llm/{client.py,prompts.py,schemas.py}
    investigate.py  repro_loop.py  test_guard.py  classify.py
    ledger.py  bisect.py  patching.py  evaluation.py
    sandbox/{base.py,docker_backend.py,remote_adapter.py,demo_backend.py}
  ui/{theme.py,components.py,pages/{dashboard,new_investigation,workspace,ledger,repro_patch,git_history,evaluation}.py}
  benchmark/{manifest.yaml, results/, recorded/}   # committed (no solutions)
  benchmark_private/                               # GIT-IGNORED: fix SHAs, patches, hidden tests
  tests/{unit/,integration/,fixtures/}
  docs/{MASTER_PROMPT.md,ARCHITECTURE.md,SECURITY.md,SETUP_WINDOWS.md,CONFIGURATION.md,DEPLOYMENT.md,BENCHMARK_REPORT.md,TEST_REPORT.md,LIMITATIONS.md,screenshots/}
  scripts/                      # helper scripts (env check, image build)
```

---

## 3. Environment setup and external blockers

Host is **Windows**. Use `pathlib` everywhere, avoid shell-specific syntax in code, write PowerShell-compatible commands in docs, and write multi-line commit messages to a temp file and use `git commit -F <file>` (avoids quoting problems).

Initial checks (record results in `PROJECT_STATE.md`):

1. Inspect the working directory; do not delete anything you did not create.
2. `git --version`, `python --version`, `docker version`, `gh --version`, `gh auth status`.
3. Verify the authenticated GitHub user is `ankush-dev-eng`.
4. Check whether `https://github.com/ankush-dev-eng/ReproLens` exists. If it exists, **reuse it safely** (clone/fetch, never overwrite, never force-push). If not, create it as a **private** repo under that account (`gh repo create ankush-dev-eng/ReproLens --private`), set `origin`, create `main` and `develop`, and work on `develop`.
5. Create a virtual environment `.venv` and install dependencies cleanly.

**External blockers** — if one occurs, record the exact remaining action in `PROJECT_STATE.md` under `BLOCKERS`, tell the user precisely what to do, and **continue all independent work**:
- GitHub CLI not authenticated → user runs `gh auth login`.
- Docker Desktop not running/installed → continue everything non-Docker; user starts Docker Desktop.
- `OPENROUTER_API_KEY` or `REPROLENS_MODEL` missing → build and test everything with mocked LLM responses; user fills `.env`.
- Streamlit Cloud deployment (needs the user's browser login) → prepare everything; the user clicks through.

Never print, log or commit secrets.

---

## 4. Git policy (mandatory)

- Remote: `https://github.com/ankush-dev-eng/ReproLens.git`. Branches: `develop` (continuous work) and `main` (always deployable; updated only by verified merges from `develop`).
- **Commit every completed atomic change** — each new module, function group, bug fix, config improvement, doc improvement, UI improvement, test improvement — and **push to `develop` immediately** (`git push origin develop`). Do not commit half-written fragments; each commit must lint cleanly and pass its related tests (a deliberately incomplete commit must be labelled `wip` in the subject and justified in the body).
- Before each commit: `ruff check .`, `ruff format --check .` (or format first), and the tests related to the change.
- Conventional commits, e.g. `feat(ast): implement Python function indexing`, `fix(sandbox): enforce execution timeout`, `test(classifier): reject unrelated test failures`, `docs(setup): add Windows installation instructions`.
- Every commit **body** must state: what was implemented · files changed · tests executed · test results (real output summary) · remaining work.
- If a push fails: read the error, retry up to 3 times, then record it in `PROJECT_STATE.md` and continue; retry on the next commit. **Never force-push. Never rewrite pushed history. Never `git reset --hard` shared history.**
- After each push, verify sync (`git status -sb`, `git rev-parse HEAD`, `git rev-parse origin/develop`) and report the commit hash.
- Update `DEVELOPMENT_LOG.md` at every milestone (and after any notable group of commits): date, milestone, commit hashes (of already-pushed commits), what was built, test results, known issues.
- Merge `develop` → `main` (`--no-ff`) only after the milestone's integration tests pass and `streamlit run main.py` boots. Tag milestones (`v0.1-slice`, `v0.2-ui`, …).
- **Never commit:** API keys, `.env`, `.streamlit/secrets.toml`, GitHub/Docker credentials, `*.db`/SQLite files, cloned repos, worktrees, `benchmark_private/`, temp/generated artifacts, `.venv`, caches. Write a comprehensive `.gitignore` first. Run a secret scan (grep for key patterns, check `git ls-files`) before every push to `main`.

---

## 5. Component specifications

### 5.1 GitHub ingestion (`github_client.py`, `models.py`)
- Parse issue URLs (`https://github.com/{owner}/{repo}/issues/{n}`), repo URLs, and `owner/repo#n`; reject everything else with a specific message. Support optional pasted issue text (used instead of or alongside API data; mark `source: pasted`).
- Use `httpx` against the GitHub REST API; optional `GITHUB_TOKEN` (for rate limits only). Fetch title, body, labels, `created_at`, `state`, author association, and comments (cap count and total characters; prefer maintainer/author comments and those containing code blocks or tracebacks).
- Handle: invalid URL; 404 (missing/private repo — state clearly that private repos are **not** supported unless a token with access is configured and actually works); 410/deleted; **pull requests** (API issues endpoint returns PRs with a `pull_request` key → reject as "not an issue"); rate limits (`X-RateLimit-Remaining`/`Reset` → friendly message with reset time); network errors with bounded retries.
- Extract from the text: code blocks, tracebacks, mentioned file paths/symbols, version strings, "expected vs actual" statements.

### 5.2 Repository engine (`repo.py`, `indexer.py`, `retrieval.py`, `refs.py`)
- Clone with `GIT_TERMINAL_PROMPT=0`, no submodule recursion, hooks disabled (`-c core.hooksPath=<empty dir>`), into a managed temp cache directory. Never execute anything from the repo on the host.
- Revision selection: explicit commit if given; benchmark manifest base commit for benchmark cases; otherwise the default-branch commit at the issue's `created_at` (`git rev-list -1 --before=...`), falling back to HEAD for open issues. Record the SHA used.
- Discover Python files (skip vendored, venv, build dirs, huge files). Build an AST index: modules, classes, functions/methods (qualified names, signatures, docstring first line, start/end lines), imports, decorators. Tolerate syntax errors per file.
- **Targeted retrieval, never whole-repo prompts:** score candidates from traceback frames (highest weight), symbols/paths named in the issue, identifier/keyword overlap, and import-graph neighbours of top hits (simple deterministic scoring; no embeddings). Return bounded excerpts with exact line numbers and a total character budget.
- **Reference verification (`refs.py`):** every file:line citation from the LLM must be checked against the checked-out SHA: path exists, line range valid, and (when a quoted snippet is supplied) whitespace-normalised snippet matches those lines. Unverified refs are stored with `verified=false`, shown as such, and never counted as source evidence.

### 5.3 OpenRouter client (`llm/client.py`)
- Endpoint `https://openrouter.ai/api/v1/chat/completions`; key from `OPENROUTER_API_KEY` (env/`.env` or `st.secrets`); model from `REPROLENS_MODEL` (**no hardcoded model IDs or keys**; optional `REPROLENS_FALLBACK_MODELS`). If unset, raise a clear configuration error.
- httpx with timeouts; bounded retries with exponential backoff and jitter; honour `Retry-After`/429; classify errors (auth, rate-limit, timeout, provider, malformed output); no retry on auth errors.
- Request JSON output; parse robustly (strip code fences); validate with Pydantic; on validation failure allow **one** corrective re-prompt, counted against retries.
- Cache responses on a hash of (model, prompt, params) in SQLite for development and tests (can be disabled by config).
- Record per-call tokens from the response `usage` field. Record cost only if the response provides it or pricing is configured; otherwise report tokens and "cost unavailable". **Never invent a cost.**
- Safe logging: redact keys and truncate bodies.
- Provide a `FakeLLM` for tests that returns scripted responses.

### 5.4 AI investigation (`llm/prompts.py`, `llm/schemas.py`, `investigate.py`)
Dedicated prompts and Pydantic schemas for: (1) issue understanding (expected vs actual behaviour, symptom statement, candidate symbols, missing information); (2) candidate root-cause investigation (ranked **hypotheses**, each with verified-checkable file:line refs and confidence label); (3) reproduction-test generation; (4) test repair; (5) optional patch generation.
Every prompt must: wrap untrusted content in delimiters and declare it data-only; require JSON matching the schema; require citations; forbid inventing files or symbols; state that hypotheses are unverified.

### 5.5 Reproduction engine (`repro_loop.py`, `test_guard.py`)
Loop: **Generate → Validate → Execute → Observe → Repair → Re-execute**, at most **3 repair attempts** per generated test.

The generated artifact is a single file `test_repro_issue_<n>.py` containing: a module-level `EXPECTED_SYMPTOM` dict (`exception_type`, `message_regex`, optional `description`, `target_symbols`), and one primary test function. It uses only the target package, stdlib and pytest, uses `tmp_path` for files, no network, no subprocess, no sleeps beyond small bounds.

**Static guard before execution (`test_guard.py`, AST-based):** reject on syntax errors; imports/calls to network, `subprocess`, `os.system`, `socket`, `ctypes`, `shutil.rmtree` outside `tmp_path`, writes outside temp dirs, `eval/exec` of external data; unconditional failures (`assert False`, bare `pytest.fail`, `raise` with no relation to repo code); `pytest.skip/xfail/importorskip`; missing `EXPECTED_SYMPTOM`; no call into the target symbols.

**Repair rules (enforced programmatically, not just in the prompt):** `EXPECTED_SYMPTOM` must be identical across attempts; assertion/`pytest.raises` count must not decrease; target-symbol calls must remain; never weaken assertions; never silently skip; never treat missing dependencies, collection errors or unrelated exceptions as reproduction. Capture real stdout/stderr (truncate at 64 KB with a marker).

### 5.6 Classification (`classify.py`)
Statuses (enum): `REPRODUCED`, `PATCH_VALIDATED`, `NOT_REPRODUCED`, `INVALID_TEST`, `ENVIRONMENT_ERROR`, `EXECUTION_TIMEOUT`. Classify from structured pytest output (use `--junitxml` plus captured output; collection errors are distinguishable from test failures), not from "exit code != 0".

A run counts as **REPRODUCED** only if **all** hold: pytest collected and ran the test; the test **failed** (not errored at collection/setup); the exception type and message match `EXPECTED_SYMPTOM`; the traceback includes at least one frame inside the target repository's source (not only the test file/stdlib); the guard passed; and the failure is **consistent across 3 executions** (record flakiness; inconsistent → `INVALID_TEST` with reason `flaky`).
- Test passes on the buggy revision → `NOT_REPRODUCED` (explain what information might be missing).
- `ModuleNotFoundError` for a third-party dependency, or image/build failure → `ENVIRONMENT_ERROR`. `ImportError`/`AttributeError` for a symbol that does not exist in the repo → `INVALID_TEST`.
- Wall-clock limit exceeded → `EXECUTION_TIMEOUT`.
- `PATCH_VALIDATED` is set only by the patch workflow (section 9).
- Optional: an LLM "symptom alignment review" may be shown, **clearly labelled as AI opinion, never as evidence**, and never used to set `REPRODUCED`.
- Cover every branch with unit tests, including adversarial ones (unconditional `assert False`, unrelated `KeyError`, collection error, missing dependency, skip, flaky).

### 5.7 Evidence ledger (`ledger.py`, `db.py`)
SQLite tables (create migrations/`CREATE TABLE IF NOT EXISTS` at startup): `investigations` (id, repo, issue number/URL, commit SHA, issue summary, final status, created_at, duration, mode), `claims` (investigation_id, kind ∈ {`HYPOTHESIS`,`SOURCE_EVIDENCE`,`EXECUTION_EVIDENCE`}, text, status, confidence), `source_refs` (path, start/end line, snippet, verified), `attempts` (attempt no., test source, status, exit code, stdout, stderr, duration, execution_origin), `patches`, `bisect_runs`, `llm_calls` (model, tokens, cost-if-known, latency), `eval_runs`. Hypotheses can only be promoted to verified by execution evidence recorded in the same investigation. Evidence must come from actual repository inspection or actual execution.

---

## 6. Docker sandbox (`sandbox/docker_backend.py`, `docker/Dockerfile.runner`)

Base image: slim Python, non-root user (UID 10001), `pytest`, `pytest-timeout`, no extras. Per-case images extend it with curated, pinned dependencies (build step only; network allowed at build, never at run).

Every test container **must** run with: `--network none`, non-root `--user 10001:10001`, `--cpus` (default 1), `--memory` and equal `--memory-swap` (default 512m), `--pids-limit` (default 128), `--cap-drop ALL`, `--security-opt no-new-privileges`, `--read-only` root filesystem with `--tmpfs /tmp` (size-limited), `-p no:cacheprovider`, an `--ulimit fsize`, a unique name and label (`reprolens=1`) for cleanup, and a hard wall-clock timeout (default 60 s) enforced by the host with `docker kill` on expiry. Mount **only** a fresh temp workspace (repo copy at the target SHA + the generated test); mount the repo read-only where possible and write only to tmpfs. **Never** mount the Docker socket, home directory, credentials or `.env`. Pass **no** environment secrets into containers. Always clean up containers and temp dirs (`finally`), and provide `python -m reprolens sandbox-clean`.

Required sandbox smoke tests (real Docker): container runs as non-root; network access fails; writing outside tmpfs fails; memory/pids/timeouts are enforced (an infinite loop test is killed and classified `EXECUTION_TIMEOUT`); host files are not visible; secrets are absent from the container environment. If Docker is unavailable, these tests are reported as **NOT RUN (Docker unavailable)** in `docs/TEST_REPORT.md` — never as passed.

---

## 7. Benchmark dataset and evaluation (`benchmark/`, `evaluation.py`)

Goal: 8–10 real, closed issues from smaller Python projects, **start with one**, then expand. Use your browser/GitHub search to find candidates. Selection criteria: closed bug with a linked fix commit that adds/changes a test; small, mostly pure-Python repo with a permissive licence; manageable dependencies (curated image feasible); reproducible with pytest; Python version known. Prefer lesser-known repos and recent issues. Record each issue's creation date and the model ID used; **do not assume a model training cutoff** — if it cannot be established, state "cutoff unknown; contamination risk not excluded".

Include **1–2 intentionally difficult or non-reproducible cases** (e.g. needs unavailable hardware/network/credentials, or ambiguous report). Synthetic repos live only in `tests/fixtures/` for unit/integration tests and must **never** be the headline demo.

Manifest (committed `benchmark/manifest.yaml`): issue URL, repo URL, buggy/base commit SHA, Python version, test dependencies, expected symptom category, expected result (`reproducible` / `not_reproducible`), licence, provenance notes. **Ground truth** (fix commit SHA, fix patch, hidden fix tests, PR content) goes only in git-ignored `benchmark_private/` and must **never** enter any LLM prompt or retrieval index (add an automated test that asserts retrieval/prompt builders cannot reach `benchmark_private/` or any commit after the base SHA — do not expose repo history beyond the base SHA to the LLM).

Evaluation harness (`python -m reprolens evaluate`): run each case live; then, **evaluation-only**, execute the final test against the fix commit to determine verified fail-to-pass. Report per case and aggregate: reproduction rate; verified fail-to-pass rate; false-reproduction rate (REPRODUCED but test also fails on fix commit); invalid-test rate; environment-error rate; time per investigation; tokens and cost (only if known). **Include failures.** Never invent or round up numbers; every number in the UI/docs must come from `eval_runs` data. Commit aggregate results and recorded per-case artifacts (labelled `recorded`, with run date, model ID, SHA) to `benchmark/results/` and `benchmark/recorded/` for Demo Mode; these contain no ground-truth patches. Generate `docs/BENCHMARK_REPORT.md` from real data.

---

## 8. Git bisect (secondary; start only after reproduction works reliably)

Two distinct goals — do not conflate them: **bug-introducing commit** (needs a known-good older and known-bad newer revision) vs **bug-fixing commit** (needs known-bad older, known-good newer). The fix commit and its parent do **not** reveal the introducing commit.

Procedure (`bisect.py`): start from the known-bad SHA. Search backwards for a known-good revision (exponential steps through release tags / commit counts, bounded depth and wall-clock budget), running the verified test in the sandbox **3 times** per revision (pass 3/3 = good, fail 3/3 with matching symptom = bad, mixed = flaky). Then binary-search between them (use `git bisect run` semantics or an equivalent own implementation using worktrees). The test file lives **outside** the repo and is copied into each temporary worktree; historical commits are never modified. If a revision cannot be tested (import/build failure, incompatible dependencies) → treat as **skip (exit code 125 semantics)**. If no known-good revision is found within bounds, output exactly: `Could not locate a known-good revision within the tested history.` Never invent a bisect result. Store every tested revision, result and run count in `bisect_runs`; show a timeline in the UI.

---

## 9. Patch generation and validation (secondary; after bisect, before final polish)

`patching.py`: start from the original buggy SHA in an isolated worktree; the LLM proposes a unified diff using the verified test as context; apply it (`git apply --check` first). A patch is `PATCH_VALIDATED` only if **all** hold: the reproduction test **fails** on the original; the **same test passes** after the patch (3/3); the repository's existing regression suite (or a curated subset defined in the manifest, with a time budget) has **no new failures** compared with the baseline run on the original. Applying cleanly is not validation. Store the exact diff, both runs and the regression comparison. Show before/after in the UI. If the baseline suite cannot be run, say so and do not mark validated.

---

## 10. Streamlit interface

Entrypoint `main.py` using `st.navigation`/`st.Page`. Original, modern developer-tool look: clean typography, dark-friendly theme in `.streamlit/config.toml`, readable code blocks, status badges, loading/progress indicators, specific error messages. Minimal animation; no decorative empty charts; **every displayed number/status comes from real data** (show empty states honestly). Header shows the execution mode (Docker / Remote / Demo) and a persistent banner in Demo Mode.

Pages: **Dashboard** (counts by status, recent investigations) · **New Investigation** (repo URL, issue URL or pasted issue, optional commit, start) · **Investigation Workspace** (live stage, repo info, issue analysis, source evidence with verified/unverified refs, hypotheses, generated test, execution results; polls DB) · **Evidence Ledger** (verified findings vs hypotheses vs AI opinions, status, execution history) · **Reproduction & Patch** (test, before/after runs, patch, regression results) · **Git History** (commit timeline, bisect results) · **Evaluation** (real metrics, success/failure breakdown, time, tokens/cost).

Configuration: `requirements.txt` (pinned, no Docker-requiring packages), `.streamlit/config.toml`, `.streamlit/secrets.toml.example` (committed), real secrets via Streamlit Secrets / `.env`. UI work must never take priority over the engine: build it after the engine's first vertical slice works end to end.

---

## 11. Security requirements (summary; document in `docs/SECURITY.md`)

Untrusted-code isolation (section 6); fail closed; no host execution; prompt-injection hardening (section 2.7) including a test with a malicious issue body and malicious source comment that attempt to change instructions/exfiltrate secrets and must have no effect; static test guard; no secrets in containers/logs/commits; bounded resource use for clone size, comments, prompt size, output size, retries and wall-clock time; path-traversal checks on all file operations; Streamlit app never executes cloned code; Demo Mode cannot execute anything; private repos unsupported unless authenticated access is genuinely implemented and tested.

---

## 12. Testing and quality assurance

Write tests as you build (tests first or alongside — never "later"). Use `FakeLLM` for deterministic tests; real LLM calls only in clearly marked optional integration/evaluation runs.

Required coverage: GitHub URL parsing; ingestion (mock HTTP incl. 404/410/PR/rate-limit); repository metadata and revision selection; AST indexing (incl. syntax-error files); retrieval scoring; source-reference validation; OpenRouter client (retries, 429, malformed JSON, schema validation, redaction); prompt-injection resistance; test guard; test generation/repair constraints (assertions not weakened, `EXPECTED_SYMPTOM` immutable); classification (every branch + adversarial cases); retry limit of 3; evidence persistence; Git operations (worktrees, rev selection) on local fixture repos; bisect on a fixture repo with a known introducing commit (incl. skip and flaky cases and the no-known-good message); patch validation logic; Docker sandbox smoke tests; benchmark-leak guard; Streamlit startup (`streamlit run main.py --server.headless true` boots and responds, or `streamlit.testing.v1.AppTest` loads every page without exceptions).

Quality gates at every milestone: clean install in a fresh venv (`pip install -r requirements.txt -r requirements-dev.txt`); `python -m compileall`; `ruff check`; `ruff format --check`; unit tests; integration tests; Docker smoke tests; Streamlit startup test; deployment-dependency check (`requirements.txt` installs cleanly with no dev-only imports in `main.py`/`ui/`). Use real output. Fix failures; never skip, delete or weaken tests to get green; mark Docker tests with a marker and report explicitly when not run.

---

## 13. Autonomous development loop (follow continuously)

1. Inspect workspace, code, environment. 2. Maintain a task checklist in `PROJECT_STATE.md`. 3. Implement the smallest next vertical slice. 4. Run it. 5. Read the **actual** terminal output. 6. On failure: capture the full error → find the root cause by inspecting code/config → make a targeted fix → re-run the failing command → run related regression tests → commit + push. Do **not** blindly retry the same failure; cap identical retries at 3, then change approach. 7. Never claim success without having examined the result. Never fabricate results, never disable tests, never fake data in the UI. 8. If a feature cannot be implemented safely, state the exact technical reason, implement the best valid alternative, and document it in `docs/LIMITATIONS.md`. 9. Update `DEVELOPMENT_LOG.md` at milestones. 10. Move to the next task. Repeat until section 16 is satisfied.

Safe-operation rules for your own commands: stay inside the project workspace and managed temp dirs; no destructive commands outside them; do not weaken Docker flags or sandbox policy to make something work; never run target-repo code on the host.

**Milestones (priority order — if time runs short, finish M6's merge/docs before M5):**
- **M0 Bootstrap:** environment checks, repo/branches, `.gitignore`, package skeleton, config, DB, CI-like local gate script (`scripts/check.ps1` + `scripts/check.sh` running the quality gates).
- **M1 Vertical slice:** Docker backend + smoke tests → GitHub ingestion → repo/AST/retrieval/refs → OpenRouter client → investigation → repro loop + guard + classifier → ledger, **driven from the CLI on ONE real benchmark issue**. Tag `v0.1-slice`.
- **M2 UI:** all pages bound to real data, background worker + polling, Demo Mode. Then capture **real screenshots** of the working UI into `docs/screenshots/` (the user needs them for the Round 1 slides).
- **M3 Benchmark:** expand to 8–10 issues incl. 1–2 hard cases; evaluation harness; recorded artifacts; `BENCHMARK_REPORT.md` from real data.
- **M4 Bisect** (section 8). **M5 Patch validation** (section 9).
- **M6 Hardening and delivery:** security review, docs, deployment prep, full gate run, merge to `main`, tag.

At the end of every milestone the app must still start and the engine must still run (always leave a demo-ready state).

---

## 14. `PROJECT_STATE.md` (create first, keep current)

Sections: `CURRENT MILESTONE` · `CHECKLIST` (done/in-progress/todo) · `LAST COMMIT` (hash, branch, pushed?) · `NEXT ACTION` (exact command/file) · `BLOCKERS` (external actions needed) · `DECISIONS` · `KNOWN ISSUES` · `ENV FACTS` (versions, Docker/gh status, chosen Python version, model ID configured). Update after every commit. If interrupted by tool/context/time limits, write the exact progress and next action here so work resumes without repeating completed steps. Do not claim background work continues after you stop.

---

## 15. Deployment preparation (Streamlit Community Cloud)

Source: `ankush-dev-eng/ReproLens`, branch `main`, main file `main.py`, deploy page `https://share.streamlit.io/deploy`. Streamlit Community Cloud is **not assumed to provide a Docker daemon** → it runs in Demo Mode (recorded, clearly labelled artifacts only). Ensure: `requirements.txt` installs on a clean venv and on the Python version chosen for the cloud app (document selecting that version in the deploy dialog's advanced settings — tell the user to verify it in the UI); app starts with **no secrets and no Docker** and shows a helpful state; secrets are read via `st.secrets` with env fallback; no absolute Windows paths; no writes outside a writable temp/app dir; the app does not crash when SQLite starts empty.

Write `docs/DEPLOYMENT.md` with exact click-by-click steps: open the deploy URL, sign in with GitHub, choose repository/branch/main file, set Python version, paste secrets in the Secrets box (template from `secrets.toml.example`; note a private repo may require granting Streamlit access to it), deploy, verify Demo Mode banner. **Do not claim a deployment was completed unless you actually verified the live URL.** Do not push unstable changes to `main`, because deployment follows it.

---

## 16. Final acceptance criteria (all must be verified with real output)

**Core:** GitHub issue ingestion · repository ingestion · AST analysis · verified source evidence · OpenRouter integration · AI investigation · pytest generation · Docker-isolated execution · correct classification · controlled repair (≤3) · evidence ledger · honest refusal mode.
**Additional:** Git bisect · patch generation and validation · benchmark evaluation on real issues (including failures).
**Application:** complete Streamlit UI on real data · root `main.py` · `requirements.txt` · Streamlit config · secrets support · Windows local setup guide · Demo Mode for the cloud.
**Engineering:** unit, integration and regression tests passing (Docker tests reported honestly) · security checks · error handling · documentation · no exposed credentials (scan evidence) · GitHub synchronised (`develop` and `main` hashes match remote) · `DEVELOPMENT_LOG.md` maintained.

**Deliverables:** complete source; repo URL; deployment-ready app; `docs/SETUP_WINDOWS.md`; `docs/ARCHITECTURE.md`; `docs/CONFIGURATION.md` (OpenRouter/GitHub/Streamlit setup); `docs/SECURITY.md`; `docs/BENCHMARK_REPORT.md`; `docs/TEST_REPORT.md` (real command outputs summarised); commit history; `docs/DEPLOYMENT.md`; `docs/LIMITATIONS.md` (known limitations and future scope).

**Final report to the user** (end of run): what works (each claim backed by a command you ran), what was not run and why, benchmark numbers exactly as measured, remaining manual steps (auth, Docker, secrets, deploy clicks), commit hashes for `develop` and `main`, and a suggested demo script for the 5–7 minute video using only features that actually work — including one case where ReproLens honestly refuses.

**Begin now:** save this prompt to `docs/MASTER_PROMPT.md`, run the environment checks, and start M0.
