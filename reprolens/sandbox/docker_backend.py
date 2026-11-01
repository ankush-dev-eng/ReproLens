"""Docker execution backend for ReproLens with strict security hardening."""

import contextlib
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from reprolens.models import ExecutionMode, ExecutionOrigin
from reprolens.sandbox.base import ExecutionBackend, ExecutionResult


def clean_sandbox_containers() -> int:
    """Find and force-remove any dangling ReproLens containers."""
    if not shutil.which("docker"):
        return 0
    try:
        res = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "label=reprolens=1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        cids = res.stdout.strip().split()
        if cids:
            subprocess.run(["docker", "rm", "-f", *cids], capture_output=True, timeout=15)
            print(f"[Sandbox] Cleaned up {len(cids)} dangling containers.")
        return 0
    except Exception as e:
        print(f"[Sandbox] Error cleaning containers: {e}")
        return 1


class DockerBackend(ExecutionBackend):
    """Executes tests inside locked-down, network-isolated Docker containers."""

    def __init__(
        self,
        image_name: str = "reprolens-runner:latest",
        cpus: str = "1",
        memory: str = "512m",
        pids_limit: int = 128,
    ) -> None:
        self.image_name = image_name
        self.cpus = cpus
        self.memory = memory
        self.pids_limit = pids_limit

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.DOCKER

    def build_container_args(
        self,
        container_name: str,
        host_workspace: Path,
        test_filename: str,
    ) -> list[str]:
        """Build the full docker run command with mandatory security flags."""
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--label",
            "reprolens=1",
            "--network",
            "none",
            "--user",
            "10001:10001",
            f"--cpus={self.cpus}",
            f"--memory={self.memory}",
            f"--memory-swap={self.memory}",
            f"--pids-limit={self.pids_limit}",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
            "--ulimit=fsize=10485760",
            "-v",
            f"{host_workspace.resolve()}:/workspace:ro",
            "-w",
            "/workspace",
            "-e",
            "PYTHONPATH=/workspace",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "TMPDIR=/tmp",
            self.image_name,
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:header",
            "--junitxml=/tmp/junit.xml",
            "-v",
            test_filename,
        ]

    def execute(
        self,
        test_source: str,
        repo_dir: Path,
        test_filename: str = "test_repro.py",
        timeout_sec: int = 60,
        env_vars: dict[str, str] | None = None,
    ) -> ExecutionResult:
        container_id = f"reprolens_{uuid.uuid4().hex[:12]}"
        temp_dir = tempfile.mkdtemp(prefix="reprolens_run_")
        temp_path = Path(temp_dir)

        start_time = time.monotonic()
        try:
            # Copy repository files into temporary workspace (skip .git to minimize size)
            for item in repo_dir.iterdir():
                if item.name == ".git":
                    continue
                dest = temp_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, symlinks=True, ignore_dangling_symlinks=True)
                else:
                    shutil.copy2(item, dest)

            # Write generated reproduction test file
            test_file_path = temp_path / test_filename
            test_file_path.write_text(test_source, encoding="utf-8")

            # Build docker command
            cmd = self.build_container_args(container_id, temp_path, test_filename)

            # Execute via subprocess with wall-clock timeout
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout_sec)
                exit_code = proc.returncode
                duration = time.monotonic() - start_time
                is_timeout = False
            except subprocess.TimeoutExpired:
                # Force kill container immediately on timeout
                with contextlib.suppress(Exception):
                    subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=5)
                proc.kill()
                stdout, stderr = proc.communicate()
                duration = time.monotonic() - start_time
                exit_code = 124
                is_timeout = True

            return ExecutionResult(
                exit_code=exit_code,
                stdout=stdout or "",
                stderr=stderr or "",
                duration_sec=duration,
                is_timeout=is_timeout,
                timed_out_after_sec=timeout_sec if is_timeout else None,
                execution_origin=ExecutionOrigin.LIVE,
                command=cmd,
            )

        finally:
            # Clean up temp directory on host
            shutil.rmtree(temp_path, ignore_errors=True)
            # Ensure container is killed if still existing
            with contextlib.suppress(Exception):
                subprocess.run(
                    ["docker", "rm", "-f", container_id],
                    capture_output=True,
                    timeout=5,
                )
