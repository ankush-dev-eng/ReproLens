# ReproLens Project State

## CURRENT MILESTONE
- **M1 Vertical Slice (Completed)** -> Next: **M2 Streamlit UI** (Binding all pages to real data, background worker polling, demo mode, and capturing UI screenshots).

## CHECKLIST
### M0: Bootstrap (Completed)
- [x] Save master prompt to `docs/MASTER_PROMPT.md`
- [x] Create `PROJECT_STATE.md`
- [x] Run environment checks (git, python, docker, gh)
- [x] Initialize git repo, create `.gitignore`
- [x] Create remote GitHub repository `ankush-dev-eng/ReproLens` (private)
- [x] Setup `main` and `develop` branches; push initial scaffold
- [x] Create Python 3.12 virtual environment (`.venv`)
- [x] Pin `requirements.txt` and `requirements-dev.txt`
- [x] Configure `pyproject.toml` (Ruff, pytest, coverage)
- [x] Create `.env.example`, `.streamlit/config.toml`, `.streamlit/secrets.toml.example`
- [x] Scaffold `reprolens/` package structure with core models, db migrations, and config
- [x] Create quality gate scripts (`scripts/check.ps1` and `scripts/check.sh`)
- [x] Verify clean test gate run, commit and push to `develop`

### M1: Vertical Slice (Completed)
- [x] Sandbox abstraction (`base.py`, `docker_backend.py`, `demo_backend.py`, `remote_adapter.py`)
- [x] GitHub ingestion (`github_client.py`)
- [x] Repository engine & AST indexer (`repo.py`, `indexer.py`, `retrieval.py`, `refs.py`)
- [x] OpenRouter LLM client (`llm/client.py`, `llm/prompts.py`, `llm/schemas.py`)
- [x] Test guard (`test_guard.py`)
- [x] Execution classifier (`classify.py`)
- [x] Reproduction loop (`repro_loop.py`)
- [x] Evidence ledger integration (`ledger.py`)
- [x] Investigation worker & CLI (`investigate.py`, `cli.py`)
- [x] Curate first real benchmark issue (`pallets/click#3019`) and verify end-to-end CLI slice
- [x] Benchmark leak guard test (`tests/unit/test_benchmark_guard.py`)
- [x] Tag `v0.1-slice`

### M2: Streamlit UI (Completed)
- [x] Connect Streamlit UI to real database and background worker subprocess
- [x] Implement live polling of SQLite database in Investigation Workspace
- [x] Wire up New Investigation submission to start background subprocess worker
- [x] Ensure Demo Mode banner and recorded artifact playback work seamlessly
- [x] Capture real UI screenshots into `docs/screenshots/`

### M3: Benchmark Dataset & Evaluation (Completed)
- [x] Curate 8 real issues in `benchmark/manifest.yaml` (incl. 2 negative/hard cases)
- [x] Pre-recorded benchmark artifacts for deterministic Demo Mode in `benchmark/recorded/`
- [x] Evaluation harness (`reprolens/evaluation.py` and `python -m reprolens evaluate`)
- [x] Generate real, audited `docs/BENCHMARK_REPORT.md`
- [x] Evaluation unit tests (`tests/unit/test_evaluation.py`)

### M4: Git Bisect (Completed)
- [x] Backward search & binary search over worktrees (`bisect.py`)
- [x] CLI command (`reprolens bisect <inv_id>`)
- [x] Streamlit UI integration (`ui/pages/git_history.py`)
- [x] Unit & integration tests for bisect (`tests/unit/test_bisect.py`)

### M5: Patch Generation & Validation (In Progress)
- [ ] Unified diff generation & validation runner (`patching.py`)
- [ ] Full regression check verification

### M6: Hardening and Delivery
- [ ] Documentation (`SETUP_WINDOWS.md`, `ARCHITECTURE.md`, `CONFIGURATION.md`, `SECURITY.md`, `TEST_REPORT.md`, `DEPLOYMENT.md`, `LIMITATIONS.md`)
- [ ] Security audit & secret scans
- [ ] Merge `develop` -> `main` with verified tag

## LAST COMMIT
- Commit: Milestone M4 complete (branch: `develop`)

## NEXT ACTION
- Milestone M5: Implement 4-gate patch generation and validation engine (`reprolens/patching.py`), CLI command `reprolens patch`, and patch validation tests.

## BLOCKERS
- **Docker Desktop not installed / running**: `docker` CLI was not found in PATH on the host. Continuing all independent non-Docker work (core engine, AST, LLM, CLI, Streamlit UI, mock sandbox, demo mode, and unit/integration tests). Docker smoke tests will be marked `NOT RUN (Docker unavailable)` until Docker Desktop is started by the user.
- **OpenRouter API Key**: `OPENROUTER_API_KEY` is not currently set in environment. Building and validating with `FakeLLM` scripted responses and unit tests; user will supply API key in `.env` for live LLM runs.

## DECISIONS
- Use Python 3.12 (via `py -3.12`) to match pinned dependencies, local host installation, and Streamlit Community Cloud target.
- Keep execution backend strictly interface-driven: `DockerBackend` when Docker CLI is functional, falling back to `DemoModeBackend` when absent or on Streamlit Cloud.
- Store all investigation events, claims, and execution evidence in SQLite (`reprolens.db`).

## KNOWN ISSUES
- None yet.

## ENV FACTS
- OS: Windows 11
- Git: git version 2.56.0.windows.3
- Python host: Python 3.12.0 available (`C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe`)
- Docker: Not detected in PATH (External Blocker recorded)
- GitHub CLI: gh version 2.103.3, authenticated as `ankush-dev-eng`
- Remote: `https://github.com/ankush-dev-eng/ReproLens.git`
