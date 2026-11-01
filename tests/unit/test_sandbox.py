"""Tests for execution sandbox backends."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from reprolens.models import ExecutionMode, ExecutionOrigin
from reprolens.sandbox.demo_backend import DemoBackend
from reprolens.sandbox.docker_backend import DockerBackend, clean_sandbox_containers


def test_docker_backend_args():
    backend = DockerBackend(image_name="test-runner:v1", cpus="2", memory="1g")
    workspace = Path("/tmp/fake_workspace")
    cmd = backend.build_container_args("repro_123", workspace, "test_foo.py")

    assert "docker" in cmd
    assert "run" in cmd
    assert "--network" in cmd and "none" in cmd
    assert "--user" in cmd and "10001:10001" in cmd
    assert "--cpus=2" in cmd
    assert "--memory=1g" in cmd
    assert "--cap-drop=ALL" in cmd
    assert "--read-only" in cmd
    assert "--label" in cmd and "reprolens=1" in cmd
    assert "--tmpfs=/tmp:rw,noexec,nosuid,size=64m" in cmd
    assert "--ulimit=fsize=10485760" in cmd
    assert "test-runner:v1" in cmd
    assert "test_foo.py" in cmd


def test_docker_backend_execute_mocked(tmp_path):
    backend = DockerBackend()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("print('hello')")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("1 passed in 0.1s\n", "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        res = backend.execute("def test_one(): assert True", repo_dir)

    assert res.exit_code == 0
    assert "1 passed" in res.stdout
    assert res.execution_origin == ExecutionOrigin.LIVE
    assert not res.is_timeout


def test_demo_backend_refusal(tmp_path):
    backend = DemoBackend(recorded_dir=tmp_path)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    res = backend.execute("def test_arbitrary(): pass", repo_dir)
    assert res.exit_code == 1
    assert "DEMO MODE REFUSAL" in res.stderr
    assert res.execution_origin == ExecutionOrigin.RECORDED
    assert backend.mode == ExecutionMode.DEMO


def test_demo_backend_serves_recorded_artifact(tmp_path):
    recorded_dir = tmp_path / "recorded"
    recorded_dir.mkdir()

    test_code = "def test_issue(): assert False"
    artifact = {
        "test_source": test_code,
        "exit_code": 1,
        "stdout": "FAIL",
        "stderr": "AssertionError",
        "duration_sec": 0.5,
        "is_timeout": False,
    }
    (recorded_dir / "case_01.json").write_text(json.dumps(artifact))

    backend = DemoBackend(recorded_dir=recorded_dir)
    res = backend.execute(test_code, tmp_path)

    assert res.exit_code == 1
    assert res.stderr == "AssertionError"
    assert res.execution_origin == ExecutionOrigin.RECORDED


def test_clean_sandbox_containers_when_no_docker(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    ret = clean_sandbox_containers()
    assert ret == 0
