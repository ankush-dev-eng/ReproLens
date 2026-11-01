# ReproLens Known Limitations & Engineering Boundaries

In keeping with our core philosophy—*"Never fabricate claims. State reality honestly."*—this document details the current engineering boundaries, failure modes, and intentional constraints of ReproLens v0.5.

---

## 1. Supported Ecosystem Boundaries

### 1.1 Pure-Python vs Native C/Rust Extensions
- **Supported:** Repositories written in pure Python (e.g. `pallets/click`, `psf/requests`, `marshmallow-code/marshmallow`, `pallets/jinja`, `pallets/flask`, `urllib3/urllib3`, `bottlepy/bottle`).
- **Limitation:** Repositories requiring heavy C-extension compilation, Fortran toolchains, or custom GPU runtimes (e.g. `numpy`, `torch`, `cryptography` with custom OpenSSL) require specialized base runner images. In the standard `reprolens-runner:latest` container, compilation tools are omitted to enforce minimal container attack surfaces.

### 1.2 Platform & OS Dependencies
- **Supported:** Bugs reproducible on Linux x86_64 or platform-independent Python semantics.
- **Limitation:** OS-specific bugs that manifest solely on Windows APIs (e.g. `winreg`, Windows named pipes, NTFS file locking) will not manifest in Linux container runners.

---

## 2. Non-Deterministic & Environmental Bugs

### 2.1 Concurrency & Race Conditions
- Bugs caused by thread-scheduling race conditions or timing windows under heavy load may pass intermittently during consistency runs. ReproLens enforces a **3-run consistency check**: if a test fails on attempt 1 but passes on attempt 2, the classifier marks it as `FLAKY` rather than declaring a verified reproduction.

### 2.2 Network-Dependent Issues
- The Docker runner executes with `--network none` to prevent command-and-control callbacks and external side effects.
- **Limitation:** Bugs that require live external HTTP endpoints (e.g. testing against a real public AWS S3 bucket) must be mocked using `unittest.mock`, `responses`, or `pytest_httpx`. If a bug cannot be reproduced with mocked networking, it cannot be safely verified in the isolated sandbox.

---

## 3. Host Environment Constraints

### 3.1 Docker Daemon Requirement for Live Arbitrary Code
- Live sandboxed execution requires a running Docker daemon (or remote runner endpoint).
- On hosts without Docker (or in cloud hosting like Streamlit Community Cloud), ReproLens safely restricts execution to verified recorded benchmark cases (**Demo Mode**) to preserve sandbox integrity.

### 3.2 LLM Reasoning Tradeoffs
- Codebase understanding relies on deterministic AST retrieval. For massive monorepos (> 100,000 files), retrieval selects the top 6 most relevant modules based on tracebacks and symbol citations. If a bug's root cause spans across unreferenced transitive dependencies in obscure sub-packages, retrieval may miss the critical file in the first attempt, requiring repair iterations.
