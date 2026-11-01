# ReproLens Test & Quality Report

> **Quality Gate Execution Date:** 2026-11-01  
> **Python Version:** 3.12.0  
> **Platform:** Windows 11 (64-bit)  
> **Test Framework:** Pytest 8.3.4 with coverage, mock, and timeout plugins  
> **Linters & Formatters:** Ruff 0.9.x  

---

## 1. Executive Summary

All automated quality gate checks passed with **100% compliance**:
- **Python Syntax Check (`compileall`):** PASSED across all modules.
- **Ruff Linter Check:** PASSED (0 errors, 0 warnings).
- **Ruff Format Check:** PASSED (all 58 files formatted).
- **Automated Pytest Suite:** **71 passed out of 71 tests (100%)** in 21.22 seconds.
- **Sensitive Secrets Scan:** PASSED (0 exposed tokens, API keys, or private files).
- **Benchmark Leak Guard:** PASSED (isolated `benchmark_private/` access strictly forbidden).

---

## 2. Test Suite Breakdown by Module

| Test Module | Test Focus | Total Tests | Status |
| :--- | :--- | :---: | :---: |
| `tests/unit/test_config.py` | Configuration resolution, paths, fallback model lists, secrets | 2 | ✅ PASS |
| `tests/unit/test_db.py` | SQLite schema migrations, foreign keys, WAL mode, CRUD for all models | 4 | ✅ PASS |
| `tests/unit/test_github_client.py` | URL/ref parsing, traceback parsing, code blocks, 404/410/429 backoff | 8 | ✅ PASS |
| `tests/unit/test_models.py` | Pydantic v2 schema validations, enums, serializations | 1 | ✅ PASS |
| `tests/unit/test_repo_and_indexer.py` | Safe git clone, worktree isolation, AST indexing, callgraphs, refs | 8 | ✅ PASS |
| `tests/unit/test_guard_and_classify.py` | AST security guard (forbidden imports, unconditional assert), multi-branch classifier | 14 | ✅ PASS |
| `tests/unit/test_sandbox.py` | Docker backend parameter hardening, DemoModeBackend playback & fail-closed | 5 | ✅ PASS |
| `tests/unit/test_llm.py` | OpenRouter client, JSON schemas, retry logic, prompt caching, FakeLLM | 7 | ✅ PASS |
| `tests/unit/test_investigate_and_loop.py` | 5-stage pipeline, iterative repair loop, ledger integration | 3 | ✅ PASS |
| `tests/unit/test_benchmark_guard.py` | Verification that `benchmark_private/` cannot be reached or leaked | 3 | ✅ PASS |
| `tests/unit/test_streamlit_app.py` | Streamlit `AppTest` headless loading, page transitions, component cards | 5 | ✅ PASS |
| `tests/unit/test_evaluation.py` | Benchmark evaluation suite, metric computation, report generation, CLI | 3 | ✅ PASS |
| `tests/unit/test_bisect.py` | Exponential backward search, binary bisect, exit code 125 skip handling | 4 | ✅ PASS |
| `tests/unit/test_patching.py` | 4-gate patch validation (baseline fail, clean apply, post-patch pass, zero regression) | 4 | ✅ PASS |
| **Total** | | **71** | **✅ 100% PASS** |

---

## 3. Quality Gate Automation Script

Every build and commit is gated by `scripts/check.ps1` (Windows) and `scripts/check.sh` (Linux/macOS):

```powershell
# Run complete verification gate
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```
