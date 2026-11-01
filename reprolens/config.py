"""Configuration management for ReproLens."""

import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# Load local .env if present
load_dotenv()


def _get_setting(key: str, default: str = "") -> str:
    """Retrieve setting from Streamlit secrets (if active) with fallback to env vars."""
    try:
        import streamlit.runtime as st_runtime

        if st_runtime.exists():
            import streamlit as st

            if hasattr(st, "secrets") and key in st.secrets:
                return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


class Config:
    """ReproLens central configuration."""

    # Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DB_PATH: Path = Path(_get_setting("REPROLENS_DB_PATH", str(PROJECT_ROOT / "reprolens.db")))

    # LLM & OpenRouter
    OPENROUTER_API_KEY: str = _get_setting("OPENROUTER_API_KEY", "")
    MODEL: str = _get_setting("REPROLENS_MODEL", "anthropic/claude-3.5-sonnet")
    FALLBACK_MODELS_RAW: str = _get_setting(
        "REPROLENS_FALLBACK_MODELS", "google/gemini-2.0-flash-exp,openai/gpt-4o-mini"
    )

    @classmethod
    def get_fallback_models(cls) -> list[str]:
        if not cls.FALLBACK_MODELS_RAW:
            return []
        return [m.strip() for m in cls.FALLBACK_MODELS_RAW.split(",") if m.strip()]

    # GitHub
    GITHUB_TOKEN: str = _get_setting("GITHUB_TOKEN", "")

    # Execution & Sandbox
    EXECUTION_MODE: str = _get_setting("REPROLENS_EXECUTION_MODE", "auto").lower()
    REMOTE_RUNNER_URL: str = _get_setting("REPROLENS_REMOTE_RUNNER_URL", "")
    CACHE_LLM: bool = _get_setting("REPROLENS_CACHE_LLM", "true").lower() in ("1", "true", "yes")

    # Timeouts & limits
    EXECUTION_TIMEOUT_SEC: int = int(_get_setting("REPROLENS_TIMEOUT_SEC", "60"))
    MAX_REPAIR_ATTEMPTS: int = 3
    MAX_FILE_SIZE_BYTES: int = 1_000_000  # 1MB limit for single file retrieval
    MAX_PROMPT_CHARS: int = 120_000

    @classmethod
    def is_docker_available(cls) -> bool:
        """Check if Docker CLI is installed and the daemon is responding."""
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def resolve_execution_mode(cls) -> str:
        """Resolve current active execution mode: docker, remote, or demo."""
        if cls.EXECUTION_MODE in ("docker", "demo", "remote"):
            if cls.EXECUTION_MODE == "remote" and not cls.REMOTE_RUNNER_URL:
                return "demo"
            if cls.EXECUTION_MODE == "docker" and not cls.is_docker_available():
                return "demo"
            return cls.EXECUTION_MODE

        # 'auto' mode
        if cls.is_docker_available():
            return "docker"
        if cls.REMOTE_RUNNER_URL:
            return "remote"
        return "demo"
