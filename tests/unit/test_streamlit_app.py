"""Tests for Streamlit application loading, pages, and components."""

from streamlit.testing.v1 import AppTest

from reprolens.db import Database
from reprolens.models import (
    Attempt,
    Claim,
    ClaimKind,
    ExecutionMode,
    ExecutionOrigin,
    Investigation,
    InvestigationStatus,
    SourceRef,
)
from ui.theme import render_status_badge


def test_main_app_loads():
    at = AppTest.from_file("main.py", default_timeout=10)
    at.run()
    assert not at.exception


def test_pages_load():
    for page in [
        "ui/pages/dashboard.py",
        "ui/pages/new_investigation.py",
        "ui/pages/workspace.py",
        "ui/pages/ledger.py",
        "ui/pages/repro_patch.py",
        "ui/pages/git_history.py",
        "ui/pages/evaluation.py",
    ]:
        at = AppTest.from_file(page, default_timeout=10)
        at.run()
        assert not at.exception, f"Exception loading {page}: {at.exception}"


def test_render_status_badge():
    for status in [
        "REPRODUCED",
        "NOT_REPRODUCED",
        "INVALID_TEST",
        "ENVIRONMENT_ERROR",
        "ANALYZING",
        "REPRODUCING",
        "PENDING",
    ]:
        html = render_status_badge(status)
        assert status in html
        assert "<span style=" in html


def test_new_investigation_submission(tmp_path, monkeypatch):
    """Test submitting the new investigation form with AppTest."""
    db_file = tmp_path / "test_reprolens.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))

    at = AppTest.from_file("ui/pages/new_investigation.py", default_timeout=10)
    at.run()
    assert not at.exception

    # Fill in inputs
    at.text_input[0].input("pallets/click")
    at.text_input[1].input("https://github.com/pallets/click/issues/3019")
    at.text_input[2].input("27aaed3fe5bcd6adedd6e91de234914af9859cf1")

    # AppTest form submit
    at.button[3].click()  # Form submit button (first 3 buttons are benchmark samples)
    at.run()
    # No crash
    assert not at.exception


def test_components_render_without_error(tmp_path, monkeypatch):
    """Verify display components execute cleanly."""
    ref = SourceRef(path="src/click/termui.py", start_line=10, end_line=15, snippet="code()")
    claim_hyp = Claim(
        id="c1",
        investigation_id="inv-1",
        kind=ClaimKind.HYPOTHESIS,
        text="A test hypothesis",
        confidence="high",
        source_ref=ref,
    )
    claim_src = Claim(
        id="c2",
        investigation_id="inv-1",
        kind=ClaimKind.SOURCE_EVIDENCE,
        text="Source citation",
        source_ref=ref,
    )

    attempt_rec = Attempt(
        id="att-1",
        investigation_id="inv-1",
        attempt_no=1,
        test_source="def test_foo(): pass",
        exit_code=1,
        stdout="AssertionError",
        stderr="",
        duration_sec=1.5,
        status=InvestigationStatus.REPRODUCED,
        execution_origin=ExecutionOrigin.RECORDED,
    )

    attempt_live = Attempt(
        id="att-2",
        investigation_id="inv-1",
        attempt_no=2,
        test_source="def test_foo(): pass",
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_sec=2.1,
        status=InvestigationStatus.NOT_REPRODUCED,
        execution_origin=ExecutionOrigin.LIVE,
    )

    # In Streamlit bare mode, calling display functions shouldn't raise unhandled exceptions
    # We test with AppTest wrapping workspace with populated db
    db_file = tmp_path / "ui_test.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)
    inv = Investigation(
        id="inv-ui-test",
        repo="pallets/click",
        issue_number=3019,
        issue_url="https://github.com/pallets/click/issues/3019",
        commit_sha="27aaed3",
        issue_summary="Test investigation",
        final_status=InvestigationStatus.REPRODUCED,
        mode=ExecutionMode.DEMO,
    )
    db.save_investigation(inv)
    db.save_claim(claim_hyp)
    db.save_claim(claim_src)
    attempt_rec.investigation_id = "inv-ui-test"
    attempt_live.investigation_id = "inv-ui-test"
    claim_hyp.investigation_id = "inv-ui-test"
    claim_src.investigation_id = "inv-ui-test"
    db.save_attempt(attempt_rec)
    db.save_attempt(attempt_live)

    at = AppTest.from_file("ui/pages/workspace.py", default_timeout=10)
    at.run()
    assert not at.exception
