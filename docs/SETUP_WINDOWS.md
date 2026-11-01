# Windows 11 Developer & User Setup Guide

This guide details how to install, configure, verify, and run ReproLens on Windows 11 using Python 3.12 and PowerShell.

---

## 1. Prerequisites

- **Windows 11** (x86_64 or ARM64)
- **Python 3.12**: Download from [python.org](https://www.python.org/downloads/release/python-3120/) or via Windows `py` launcher:
  ```powershell
  py -3.12 --version
  # Output should show: Python 3.12.x
  ```
- **Git for Windows**: Git CLI 2.40+ installed and on PATH.
- **Docker Desktop for Windows** *(Optional)*:
  - If Docker Desktop is running with WSL 2 backend, live sandboxed container execution is enabled automatically.
  - If Docker Desktop is not installed or stopped, ReproLens runs in **Demo Mode**, safely serving verified recorded benchmark runs.

---

## 2. Clone and Setup Virtual Environment

1. Clone the repository and navigate into the project directory:
   ```powershell
   git clone https://github.com/ankush-dev-eng/ReproLens.git
   cd ReproLens
   ```

2. Create a Python 3.12 virtual environment:
   ```powershell
   py -3.12 -m venv .venv
   ```

3. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   *(If script execution is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

4. Install pinned dependencies and development tools:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

---

## 3. Configuration (`.env`)

Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Open `.env` and set your credentials:
```ini
# OpenRouter API Key for Reasoning LLM (Optional: Leave blank to use scripted benchmark mode)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Reasoning Models
REPROLENS_MODEL=anthropic/claude-3.5-sonnet
REPROLENS_FALLBACK_MODELS=google/gemini-2.0-flash-exp,openai/gpt-4o-mini

# GitHub Token (Optional: Increases rate limit from 60 to 5,000 req/hr)
GITHUB_TOKEN=your_personal_github_token_here

# Database path (Defaults to reprolens.db in project root)
REPROLENS_DB_PATH=reprolens.db
```

---

## 4. Run Quality Gate Checks

Execute the automated test and linting suite:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

The script runs:
1. Python compileall syntax verification
2. Ruff linter check
3. Ruff code format check
4. Pytest unit & integration test suite (71+ tests)
5. Sensitive secrets & API key pattern scan
6. Docker sandbox smoke test check (auto-detects Docker presence)

---

## 5. Launch Streamlit Web UI

Start the interactive dashboard:
```powershell
streamlit run main.py
```

The app will open automatically in your browser at `http://localhost:8501`.

### UI Features:
- **📊 Dashboard**: Global metrics, recent triage runs, and 1-click quick-launch benchmark buttons.
- **➕ New Investigation**: Input issue URLs or click pre-filled samples.
- **🔬 Investigation Workspace**: Real-time progress bar across 5 reproduction stages, minimal reproducer test code, execution evidence cards, and download button.
- **📜 Evidence Ledger**: Clear separation of AI hypotheses vs AST-verified source citations.
- **🩹 Reproduction & Patch**: 4-gate candidate fix verification and diff inspection.
- **🌿 Git History & Bisect**: Automated regression bisection runner and commit timeline.
- **📈 Benchmark Evaluation**: Audited multi-case benchmark suite results and accuracy report.

---

## 6. Command-Line Workflows

ReproLens provides a complete CLI interface via `python -m reprolens`:

### 6.1 Reproduce an Issue
```powershell
# Triage and reproduce an issue directly
python -m reprolens reproduce https://github.com/pallets/click/issues/3019 --commit 27aaed3fe5bcd6adedd6e91de234914af9859cf1
```

### 6.2 Inspect System and Investigation Status
```powershell
# View recent investigations
python -m reprolens status

# View detailed status of a specific investigation
python -m reprolens status inv-d27c379e
```

### 6.3 Run Benchmark Evaluation Suite
```powershell
# Evaluate all 8 benchmark cases and generate docs/BENCHMARK_REPORT.md
python -m reprolens evaluate
```

### 6.4 Automated Git Bisect
```powershell
# Bisect repository history to locate regression-introducing commit
python -m reprolens bisect <investigation_id>
```

### 6.5 4-Gate Patch Validation
```powershell
# Generate candidate fix and execute 4-gate validation
python -m reprolens patch <investigation_id>
```
