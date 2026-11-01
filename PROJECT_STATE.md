# ReproLens Project State

## CURRENT MILESTONE
- **M0 Bootstrap**: Repository setup, environment verification, base project layout, dependencies, configuration, SQLite database schema, and test/gate scripts.

## CHECKLIST
### M0: Bootstrap (In Progress)
- [x] Save master prompt to `docs/MASTER_PROMPT.md`
- [x] Create `PROJECT_STATE.md`
- [x] Run environment checks (git, python, docker, gh)
- [ ] Initialize git repo, create `.gitignore`
- [ ] Create remote GitHub repository `ankush-dev-eng/ReproLens` (private)
- [ ] Setup `main` and `develop` branches; push initial scaffold
- [ ] Create Python 3.12 virtual environment (`.venv`)
- [ ] Pin `requirements.txt` and `requirements-dev.txt`
- [ ] Configure `pyproject.toml` (Ruff, pytest, coverage)
- [ ] Create `.env.example`, `.streamlit/config.toml`, `.streamlit/secrets.toml.example`
- [ ] Scaffold `reprolens/` package structure with core models, db migrations, and config
- [ ] Create quality gate scripts (`scripts/check.ps1` and `scripts/check.sh`)
- [ ] Verify clean test gate run, commit and push to `develop`

### M1: Vertical Slice (Next)
- [ ] Sandbox abstraction (`base.py`, `docker_backend.py`, `demo_backend.py`)
- [ ] GitHub ingestion (`github_client.py`, `models.py`)
- [ ] Repository engine & AST indexer (`repo.py`, `indexer.py`, `retrieval.py`, `refs.py`)
- [ ] OpenRouter LLM client (`llm/client.py`, `llm/prompts.py`, `llm/schemas.py`)
- [ ] Investigation orchestrator (`investigate.py`)
- [ ] Reproduction loop & test guard (`repro_loop.py`, `test_guard.py`)
- [ ] Execution classifier (`classify.py`)
- [ ] Evidence ledger (`ledger.py`, `db.py`)
- [ ] End-to-end CLI slice on one real benchmark issue (`cli.py`, `__main__.py`)
- [ ] Tag `v0.1-slice`

### M2: Streamlit UI
- [ ] Streamlit pages & components (`main.py`, `ui/`)
- [ ] Background worker subprocess & DB polling
- [ ] Demo Mode backend with pre-approved recorded artifacts
- [ ] Capture UI screenshots into `docs/screenshots/`

### M3: Benchmark Dataset & Evaluation
- [ ] Curate 8-10 real issues in `benchmark/manifest.yaml` (incl. 1-2 negative/hard cases)
- [ ] Evaluation harness (`evaluation.py`)
- [ ] Generate real `docs/BENCHMARK_REPORT.md`

### M4: Git Bisect
- [ ] Backward search & binary search over worktrees (`bisect.py`)
- [ ] Unit & integration tests for bisect

### M5: Patch Generation & Validation
- [ ] Unified diff generation & validation runner (`patching.py`)
- [ ] Full regression check verification

### M6: Hardening and Delivery
- [ ] Documentation (`SETUP_WINDOWS.md`, `ARCHITECTURE.md`, `CONFIGURATION.md`, `SECURITY.md`, `TEST_REPORT.md`, `DEPLOYMENT.md`, `LIMITATIONS.md`)
- [ ] Security audit & secret scans
- [ ] Merge `develop` -> `main` with verified tag

## LAST COMMIT
- None (pre-initial commit)

## NEXT ACTION
- Initialize git repo, create `.gitignore`, create remote private repository `ankush-dev-eng/ReproLens`, set branches `main` and `develop`.

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
