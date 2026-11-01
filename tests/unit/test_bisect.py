"""Tests for automated git bisect engine and isolated worktree search."""

from pathlib import Path
from unittest.mock import MagicMock

from reprolens.bisect import BisectResult, GitBisectEngine
from reprolens.cli import main
from reprolens.db import Database
from reprolens.models import ExecutionMode, Investigation, InvestigationStatus
from reprolens.sandbox.base import ExecutionBackend, ExecutionResult


class MockBisectBackend(ExecutionBackend):
    """Mock execution backend simulating commit test outcomes."""

    def __init__(self, good_commits: set[str], bad_commits: set[str]) -> None:
        self.good_commits = good_commits
        self.bad_commits = bad_commits

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
        # Determine commit from repo_dir or mock
        return ExecutionResult(
            exit_code=1,
            stdout="AssertionError: regression",
            stderr="",
            duration_sec=0.1,
            is_timeout=False,
        )


def test_bisect_revision_testing(tmp_path, monkeypatch):
    """Verify test_revision executes runs and saves BisectRun in database."""
    db_file = tmp_path / "test_bisect.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    backend = MagicMock(spec=ExecutionBackend)
    backend.execute.return_value = ExecutionResult(
        exit_code=0, stdout="1 passed", stderr="", duration_sec=0.1, is_timeout=False
    )

    repo_mgr = MagicMock()
    repo_mgr.checkout_worktree.return_value = tmp_path / "wt"
    repo_mgr.cleanup_worktree.return_value = None

    engine = GitBisectEngine(
        repo_dir=tmp_path,
        backend=backend,
        db=db,
        repo_mgr=repo_mgr,
    )

    run = engine.test_revision("inv-123", "commit-abc", "def test(): pass", runs=3)
    assert run.status == "good"
    assert run.pass_count == 3
    assert run.fail_count == 0

    # Verify saved in DB
    records = db.list_bisect_runs("inv-123")
    assert len(records) == 1
    assert records[0].commit_sha == "commit-abc"
    assert records[0].status == "good"


def test_bisect_skip_code_125(tmp_path, monkeypatch):
    """Verify exit code 125 is marked as skip."""
    db_file = tmp_path / "test_bisect_skip.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    backend = MagicMock(spec=ExecutionBackend)
    backend.execute.return_value = ExecutionResult(
        exit_code=125, stdout="", stderr="build error", duration_sec=0.1, is_timeout=False
    )

    repo_mgr = MagicMock()
    repo_mgr.checkout_worktree.return_value = tmp_path / "wt"
    repo_mgr.cleanup_worktree.return_value = None

    engine = GitBisectEngine(
        repo_dir=tmp_path,
        backend=backend,
        db=db,
        repo_mgr=repo_mgr,
    )

    run = engine.test_revision("inv-123", "commit-skip", "def test(): pass", runs=3)
    assert run.status == "skip"


def test_bisect_end_to_end(tmp_path, monkeypatch):
    """Verify bisect engine identifies culprit commit."""
    db_file = tmp_path / "test_bisect_e2e.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    backend = MagicMock(spec=ExecutionBackend)
    # Return fail on buggy, pass on good
    backend.execute.side_effect = [
        ExecutionResult(exit_code=1, stdout="FAIL", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=1, stdout="FAIL", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=1, stdout="FAIL", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False),
    ]

    repo_mgr = MagicMock()
    repo_mgr.checkout_worktree.return_value = tmp_path / "wt"
    repo_mgr.cleanup_worktree.return_value = None

    engine = GitBisectEngine(
        repo_dir=tmp_path,
        backend=backend,
        db=db,
        repo_mgr=repo_mgr,
    )

    monkeypatch.setattr(engine, "get_commit_ancestry", lambda sha, limit: ["bad_sha", "good_sha"])
    monkeypatch.setattr(
        engine,
        "get_commit_metadata",
        lambda sha: {"subject": "Fix commit", "author": "Alice", "date": "2026"},
    )

    res = engine.bisect(
        investigation_id="inv-e2e",
        buggy_commit="bad_sha",
        test_source="def test(): pass",
    )

    assert isinstance(res, BisectResult)
    assert res.success is True
    assert res.culprit_commit is not None


def test_cli_bisect_command(tmp_path, monkeypatch):
    """Verify 'reprolens bisect' CLI command execution."""
    db_file = tmp_path / "test_cli_bisect.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    inv = Investigation(
        id="inv-cli-bisect",
        repo="pallets/click",
        issue_number=3019,
        issue_url="https://github.com/pallets/click/issues/3019",
        commit_sha="c096a10",
        issue_summary="Bisect test",
        final_status=InvestigationStatus.REPRODUCED,
    )
    db.save_investigation(inv)

    from reprolens.models import Attempt, ExecutionOrigin

    attempt = Attempt(
        id="att-cli",
        investigation_id="inv-cli-bisect",
        attempt_no=1,
        test_source="def test(): pass",
        exit_code=1,
        stdout="FAIL",
        stderr="",
        duration_sec=0.1,
        status=InvestigationStatus.REPRODUCED,
        execution_origin=ExecutionOrigin.DEMO
        if hasattr(ExecutionOrigin, "DEMO")
        else ExecutionOrigin.RECORDED,
    )
    db.save_attempt(attempt)

    # Invoke CLI bisect
    exit_code = main(["bisect", "inv-cli-bisect"])
    assert exit_code == 0
