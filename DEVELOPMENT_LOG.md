# ReproLens Development Log

This log records the timeline, completed milestones, commit hashes, verified test outputs, and known issues throughout development.

---

## [2026-11-01] Milestone M0: Project Initialization & Environment Setup (Completed)
- **Status:** Completed
- **Commit:** `40bdb58` (pushed to `origin/main` and `origin/develop`)
- **Built:**
  - Saved `docs/MASTER_PROMPT.md` verbatim from specification.
  - Initialized `PROJECT_STATE.md` with milestone tracking, blockers, and environment facts.
  - Created remote private repository `ankush-dev-eng/ReproLens` and established `main` and `develop` branches.
  - Setup Python 3.12 `.venv` with pinned dependencies (`requirements.txt`, `requirements-dev.txt`).
  - Configured `pyproject.toml` with Ruff rules and strict pytest markers.
  - Implemented core Pydantic v2 data models (`reprolens/models.py`) and SQLite database persistence (`reprolens/db.py`).
  - Implemented configuration management with Streamlit secrets fallback (`reprolens/config.py`).
  - Implemented CLI entrypoint (`reprolens/cli.py`, `reprolens/__main__.py`).
  - Built modern Streamlit multi-page UI architecture with `st.navigation` (`main.py`, `ui/`).
  - Created automated quality gate check scripts (`scripts/check.ps1`, `scripts/check.sh`).
  - Authored unit test suite for config, models, database, and Streamlit app startup.
- **Test Results:** 9 passed in 3.06s. All quality gate checks (compileall, ruff check, ruff format, pytest, secret scan) passed cleanly.
- **Known Issues / Blockers:**
  - Docker CLI not installed/in PATH on host: Recorded as external blocker; continuing with mock/Demo execution backend. Live Docker tests cleanly marked and reported.
  - `OPENROUTER_API_KEY` not yet populated in host environment: `FakeLLM` scripted harness provided for tests.

---

## [2026-11-01] Milestone M1: Vertical Slice (Started)
- **Status:** In Progress
- **Next steps:** Implement sandbox execution backends (`base.py`, `docker_backend.py`, `demo_backend.py`), GitHub issue client, AST parser, OpenRouter LLM client, and reproduction pipeline.
