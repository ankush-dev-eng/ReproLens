# ReproLens

> **AI-Powered GitHub Issue Reproduction Engine**  
> *"Don't trust the diagnosis. Trust the failing test."*

ReproLens turns GitHub issues into executable, isolated pytest reproductions that fail for the reported reason, or clearly explains why the issue could not be reproduced.

---

## Key Differentiators

- **Reproduction-First Triage:** Prioritizes creating deterministic, minimal pytest repros before suggesting code modifications.
- **Auditable Evidence Ledger:** Strict separation of hypotheses, verified source citations, and executed container evidence.
- **Honest Refusal Mode:** Refuses to declare reproduction if environment dependencies cannot be met or test failure does not match the issue symptom.
- **Multi-Attempt Repair Loop:** Enforces non-weakened assertions across at most 3 repair iterations.
- **Sandboxed Docker Execution:** Strict isolation (`--network none`, non-root, read-only rootfs, tmpfs writes only, ulimits, timeouts).

## Architecture

ReproLens consists of:
1. **Core Engine (`reprolens/`):** Python library containing GitHub ingestion, AST indexer, targeted retrieval, OpenRouter LLM client, reproduction loop, and SQLite evidence ledger.
2. **CLI (`python -m reprolens`):** Standalone interface for headless investigations and evaluation.
3. **Execution Sandbox:** Docker backend for full containment; falls back to Demo Mode with recorded benchmark evidence when Docker is unavailable (e.g. Streamlit Community Cloud).
4. **Streamlit UI (`main.py`, `ui/`):** Multi-page investigation workspace, evidence ledger, diff inspector, and evaluation viewer.

## Quick Start (Windows)

```powershell
# 1. Clone repository
git clone https://github.com/ankush-dev-eng/ReproLens.git
cd ReproLens

# 2. Setup virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 4. Configure environment
Copy-Item .env.example .env
# Edit .env with your OPENROUTER_API_KEY and REPROLENS_MODEL

# 5. Run tests & quality gate
.\scripts\check.ps1

# 6. Start Streamlit UI
streamlit run main.py
```

## Licence

MIT License. See LICENSE file for details.

