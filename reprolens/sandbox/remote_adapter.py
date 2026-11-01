"""Remote runner adapter for ReproLens when a dedicated remote execution cluster is configured."""

from pathlib import Path

import httpx

from reprolens.config import Config
from reprolens.models import ExecutionMode, ExecutionOrigin
from reprolens.sandbox.base import ExecutionBackend, ExecutionResult


class RemoteRunnerBackend(ExecutionBackend):
    """Executes tests via a remote sandboxed HTTP runner."""

    def __init__(self, runner_url: str | None = None) -> None:
        self.runner_url = runner_url or Config.REMOTE_RUNNER_URL
        if not self.runner_url:
            raise ValueError(
                "REPROLENS_REMOTE_RUNNER_URL must be configured for RemoteRunnerBackend."
            )

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.REMOTE

    def execute(
        self,
        test_source: str,
        repo_dir: Path,
        test_filename: str = "test_repro.py",
        timeout_sec: int = 60,
        env_vars: dict[str, str] | None = None,
    ) -> ExecutionResult:
        payload = {
            "test_source": test_source,
            "test_filename": test_filename,
            "timeout_sec": timeout_sec,
            "env_vars": env_vars or {},
        }
        with httpx.Client(timeout=float(timeout_sec + 10)) as client:
            resp = client.post(f"{self.runner_url.rstrip('/')}/run", json=payload)
            resp.raise_for_status()
            data = resp.json()

            return ExecutionResult(
                exit_code=data.get("exit_code", 1),
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                duration_sec=data.get("duration_sec", 0.0),
                is_timeout=data.get("is_timeout", False),
                execution_origin=ExecutionOrigin.LIVE,
            )
