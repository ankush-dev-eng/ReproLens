"""Tests for candidate patch generation and 4-gate validation engine."""

from unittest.mock import MagicMock

from reprolens.cli import main
from reprolens.db import Database
from reprolens.models import (
    Attempt,
    ExecutionOrigin,
    Investigation,
    InvestigationStatus,
)
from reprolens.patching import (
    PatchEngine,
    PatchValidationResult,
    validate_diff_syntax,
)
from reprolens.sandbox.base import ExecutionBackend, ExecutionResult


def test_validate_diff_syntax():
    valid_diff = """--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
-old_code
+new_code
"""
    assert validate_diff_syntax(valid_diff) is True
    assert validate_diff_syntax("not a diff") is False
    assert validate_diff_syntax("") is False


def test_patch_validation_all_gates_pass(tmp_path, monkeypatch):
    """Verify complete 4-gate patch validation success."""
    db_file = tmp_path / "test_patch.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    inv = Investigation(
        id="inv-patch-1",
        repo="pallets/click",
        issue_number=3019,
        issue_url="https://github.com/pallets/click/issues/3019",
        commit_sha="c096a10",
        issue_summary="Click patch test",
        final_status=InvestigationStatus.REPRODUCED,
    )
    db.save_investigation(inv)

    backend = MagicMock(spec=ExecutionBackend)
    # Gate 1: Baseline run fails (exit code 1)
    # Gate 3: 3 post-patch runs pass (exit code 0)
    backend.execute.side_effect = [
        ExecutionResult(exit_code=1, stdout="FAIL", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False),
        ExecutionResult(exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False),
    ]

    repo_mgr = MagicMock()
    repo_mgr.checkout_worktree.return_value = tmp_path / "wt"
    repo_mgr.cleanup_worktree.return_value = None

    # Mock git apply
    monkeypatch.setattr("reprolens.patching._run_git", lambda cmd, cwd: "")

    engine = PatchEngine(backend=backend, db=db, repo_mgr=repo_mgr)
    diff = """--- a/foo.py\n+++ b/foo.py\n@@ -1,2 +1,2 @@\n-old\n+new\n"""

    res = engine.validate_patch(
        investigation_id="inv-patch-1",
        repo_dir=tmp_path,
        base_commit="c096a10",
        test_source="def test(): pass",
        diff=diff,
    )

    assert isinstance(res, PatchValidationResult)
    assert res.gate1_baseline_failed is True
    assert res.gate2_patch_applied is True
    assert res.gate3_post_patch_passed is True
    assert res.gate4_regression_clean is True
    assert res.final_status == InvestigationStatus.PATCH_VALIDATED

    # Verify updated investigation in DB
    updated_inv = db.get_investigation("inv-patch-1")
    assert updated_inv.final_status == InvestigationStatus.PATCH_VALIDATED


def test_patch_validation_gate1_rejection(tmp_path, monkeypatch):
    """Verify rejection when baseline test passes (Gate 1 fails)."""
    db_file = tmp_path / "test_patch_g1.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    backend = MagicMock(spec=ExecutionBackend)
    # Gate 1: Baseline passes unexpectedly
    backend.execute.return_value = ExecutionResult(
        exit_code=0, stdout="PASS", stderr="", duration_sec=0.1, is_timeout=False
    )

    repo_mgr = MagicMock()
    repo_mgr.checkout_worktree.return_value = tmp_path / "wt"
    repo_mgr.cleanup_worktree.return_value = None

    engine = PatchEngine(backend=backend, db=db, repo_mgr=repo_mgr)
    res = engine.validate_patch(
        investigation_id="inv-g1",
        repo_dir=tmp_path,
        base_commit="c096a10",
        test_source="def test(): pass",
        diff="--- a/foo.py\n+++ b/foo.py\n@@ -1,1 +1,1 @@\n",
    )

    assert res.gate1_baseline_failed is False
    assert "Gate 1 Failed" in res.details


def test_cli_patch_command(tmp_path, monkeypatch):
    """Verify 'reprolens patch' CLI command execution."""
    db_file = tmp_path / "test_cli_patch.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    inv = Investigation(
        id="inv-cli-patch",
        repo="pallets/click",
        issue_number=3019,
        issue_url="https://github.com/pallets/click/issues/3019",
        commit_sha="c096a10",
        issue_summary="Patch CLI test",
        final_status=InvestigationStatus.REPRODUCED,
    )
    db.save_investigation(inv)

    attempt = Attempt(
        id="att-patch-cli",
        investigation_id="inv-cli-patch",
        attempt_no=1,
        test_source="def test(): pass",
        exit_code=1,
        stdout="FAIL",
        stderr="",
        duration_sec=0.1,
        status=InvestigationStatus.REPRODUCED,
        execution_origin=ExecutionOrigin.RECORDED,
    )
    db.save_attempt(attempt)

    # Mock git operations and patch validation
    patch_file = tmp_path / "sample.patch"
    patch_file.write_text("--- a/foo\n+++ b/foo\n@@ -1 +1 @@\n", encoding="utf-8")

    monkeypatch.setattr("reprolens.patching._run_git", lambda cmd, cwd: "")

    exit_code = main(["patch", "inv-cli-patch", "--patch-file", str(patch_file)])
    assert exit_code == 0
