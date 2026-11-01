# ReproLens Deployment Guide

ReproLens is designed for straightforward deployment on **Streamlit Community Cloud**, **Local Workstations**, or **Self-Hosted Virtual Machines** with Docker.

---

## 1. Streamlit Community Cloud (Recommended for Demo)

Streamlit Community Cloud runs in unprivileged container environments without access to a nested Docker daemon.
ReproLens includes native support for this through **Demo Mode**:

### Steps to Deploy:
1. Fork or push the repository to GitHub: `ankush-dev-eng/ReproLens`.
2. Ensure the `main` branch is selected.
3. Log in to [share.streamlit.io](https://share.streamlit.io/).
4. Click **New app**:
   - **Repository:** `ankush-dev-eng/ReproLens`
   - **Branch:** `main`
   - **Main file path:** `main.py`
5. Under **Advanced settings**, set your environment secrets:
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-..."
   GITHUB_TOKEN = "ghp_..."
   REPROLENS_EXEC_MODE = "demo"
   ```
6. Click **Deploy!**

### Cloud Runtime Guarantees:
- ReproLens detects the lack of a Docker daemon and displays the **Demo Mode** indicator banner.
- Users and hackathon judges can navigate the pre-populated benchmark suite (e.g. Click #3019, Marshmallow #1842, Requests #3367), trigger investigations, inspect the evidence ledger, download minimal reproducer scripts, run bisect timelines, and view patch validation without needing Docker.

---

## 2. Self-Hosted Server Deployment (with Live Docker Sandbox)

To enable live execution of arbitrary repositories inside hardened Docker containers:

### 2.1 Host Requirements:
- Ubuntu 22.04 LTS / Debian 12 / Windows 11 with Docker Engine 24.0+
- Python 3.12+
- Git 2.40+

### 2.2 Build the Runner Container:
Build the unprivileged sandbox image:
```bash
docker build -t reprolens-runner:latest -f docker/Dockerfile.runner .
```

### 2.3 Verify Container Capabilities:
Ensure the container runs as unprivileged user `10001`:
```bash
docker run --rm reprolens-runner:latest id
# Expected output: uid=10001(sandbox) gid=10001(sandbox) groups=10001(sandbox)
```

### 2.4 Run Streamlit in Background:
```bash
nohup streamlit run main.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
```

---

## 3. Remote Sandbox Runner Cluster (`RemoteRunnerBackend`)

For enterprise or multi-tenant deployments where the Streamlit web front-end is physically separated from code execution nodes:
1. Deploy the runner microservice on an isolated worker pool.
2. Set `REPROLENS_EXEC_MODE=remote` and `REPROLENS_RUNNER_URL=https://runner.internal:50051`.
3. The front-end delivers test code via HTTPS/mTLS and polls execution output securely.
