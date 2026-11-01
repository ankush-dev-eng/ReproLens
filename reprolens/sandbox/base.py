"""Base abstraction for ReproLens test execution backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from reprolens.models import ExecutionMode, ExecutionOrigin


@dataclass
class ExecutionResult:
    """Standardized output from running a test inside an execution backend."""

    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    is_timeout: bool = False
    timed_out_after_sec: int | None = None
    execution_origin: ExecutionOrigin = ExecutionOrigin.LIVE
    command: list[str] | None = None


class ExecutionBackend(ABC):
    """Abstract interface for sandboxed test execution."""

    @property
    @abstractmethod
    def mode(self) -> ExecutionMode:
        """The execution mode implemented by this backend."""
        pass

    @abstractmethod
    def execute(
        self,
        test_source: str,
        repo_dir: Path,
        test_filename: str = "test_repro.py",
        timeout_sec: int = 60,
        env_vars: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute a test source against a repository checkout.

        Args:
            test_source: The Python pytest code to run.
            repo_dir: Path to the target repository checkout.
            test_filename: Name of the test file inside the container.
            timeout_sec: Hard timeout in seconds.
            env_vars: Environment variables to inject (no secrets allowed).
        """
        pass
