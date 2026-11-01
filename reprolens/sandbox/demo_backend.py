"""Demo Mode backend for Streamlit Cloud and environments without Docker."""

import json
from pathlib import Path

from reprolens.config import Config
from reprolens.models import ExecutionMode, ExecutionOrigin
from reprolens.sandbox.base import ExecutionBackend, ExecutionResult


class DemoBackend(ExecutionBackend):
    """Fallback backend serving pre-approved recorded benchmark artifacts.

    Refuses to execute arbitrary, unverified code to preserve sandbox safety.
    """

    def __init__(self, recorded_dir: Path | None = None) -> None:
        self.recorded_dir = recorded_dir or (Config.PROJECT_ROOT / "benchmark" / "recorded")

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.DEMO

    def execute(
        self,
        test_source: str,
        repo_dir: Path,
        test_filename: str = "test_repro.py",
        timeout_sec: int = 60,
        env_vars: dict[str, str] | None = None,
    ) -> ExecutionResult:
        # Check if there is an exact matching recorded artifact in benchmark/recorded
        if self.recorded_dir.exists():
            for artifact_path in self.recorded_dir.glob("*.json"):
                try:
                    data = json.loads(artifact_path.read_text(encoding="utf-8"))
                    # If recorded test source or case matches
                    if data.get("test_source", "").strip() == test_source.strip():
                        return ExecutionResult(
                            exit_code=data.get("exit_code", 1),
                            stdout=data.get("stdout", ""),
                            stderr=data.get("stderr", ""),
                            duration_sec=data.get("duration_sec", 1.0),
                            is_timeout=data.get("is_timeout", False),
                            execution_origin=ExecutionOrigin.RECORDED,
                        )
                except Exception:
                    continue

        # Fail closed: Live execution is strictly forbidden in Demo Mode
        refusal_msg = (
            "DEMO MODE REFUSAL: Live execution is disabled in Demo Mode. "
            "No matching pre-recorded benchmark artifact was found for this test source. "
            "To run live executions, launch ReproLens in an environment with Docker Desktop enabled."
        )
        return ExecutionResult(
            exit_code=1,
            stdout="",
            stderr=refusal_msg,
            duration_sec=0.01,
            is_timeout=False,
            execution_origin=ExecutionOrigin.RECORDED,
        )
