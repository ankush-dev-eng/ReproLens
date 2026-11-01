# ReproLens Configuration Reference

ReproLens is configured via environment variables, `.env` files, and Streamlit secrets.
Configuration is centralized in `reprolens/config.py` and supports dynamic overrides.

---

## 1. Environment Variables Reference

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | `""` | API key for OpenRouter reasoning models. If unset, ReproLens operates in offline scripted benchmark mode. |
| `REPROLENS_MODEL` | `anthropic/claude-3.5-sonnet` | Primary model identifier passed to OpenRouter for issue understanding, root-cause hypotheses, and test synthesis. |
| `REPROLENS_FALLBACK_MODELS` | `google/gemini-2.0-flash-exp,openai/gpt-4o-mini` | Comma-separated list of fallback models invoked sequentially if the primary model encounters rate limits (429) or timeouts. |
| `GITHUB_TOKEN` | `""` | GitHub Personal Access Token (`read:public_repo`). Increases rate limit from 60 requests/hr (anonymous) to 5,000 requests/hr. |
| `REPROLENS_DB_PATH` | `<root>/reprolens.db` | Absolute or relative path to the SQLite storage database. |
| `REPROLENS_EXEC_MODE` | `auto` | Execution mode override: `auto` (auto-detects Docker daemon), `docker` (forces live container execution), `remote` (remote runner), or `demo` (forces recorded playback). |
| `REPROLENS_DOCKER_IMAGE` | `reprolens-runner:latest` | Docker image tag utilized for isolated test runner containers. |
| `REPROLENS_RUNNER_URL` | `""` | HTTP/gRPC endpoint URL for remote runner cluster (when `REPROLENS_EXEC_MODE=remote`). |

---

## 2. Pinned Engine Constants

These thresholds are enforced in `reprolens/config.py` to preserve deterministic behavior and resource bounds:

- **`MAX_REPAIR_ATTEMPTS = 3`**: Maximum number of iterative test repair attempts per investigation.
- **`TEST_TIMEOUT_SEC = 60`**: Wall-clock execution timeout in seconds before container processes receive hard termination (`SIGKILL`).
- **`CONSISTENCY_RUNS = 3`**: Required consecutive passing runs to establish `NOT_REPRODUCED` status or `PATCH_VALIDATED` verification.
- **`MAX_OUTPUT_CHARS = 65536`**: Maximum captured standard output and standard error bytes (64 KB) to prevent memory blowup from verbose logs.

---

## 3. Streamlit Cloud Secrets Configuration

When deploying to **Streamlit Community Cloud**, secrets can be configured in `.streamlit/secrets.toml` or the Streamlit Cloud dashboard:

```toml
# .streamlit/secrets.toml
OPENROUTER_API_KEY = "sk-or-v1-..."
REPROLENS_MODEL = "anthropic/claude-3.5-sonnet"
GITHUB_TOKEN = "ghp_..."
REPROLENS_EXEC_MODE = "demo"
```
