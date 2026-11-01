"""Tests for Database and Ledger SQLite storage."""

from reprolens.db import Database
from reprolens.models import (
    Attempt,
    Claim,
    ClaimKind,
    ClaimStatus,
    ExecutionMode,
    ExecutionOrigin,
    Investigation,
    InvestigationStatus,
    SourceRef,
)


def test_db_investigation_lifecycle(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    inv = Investigation(
        id="test-inv-1",
        repo="pallets/click",
        issue_number=100,
        issue_url="https://github.com/pallets/click/issues/100",
        final_status=InvestigationStatus.ANALYZING,
        mode=ExecutionMode.DEMO,
    )
    db.save_investigation(inv)

    fetched = db.get_investigation("test-inv-1")
    assert fetched is not None
    assert fetched.repo == "pallets/click"
    assert fetched.final_status == InvestigationStatus.ANALYZING

    # Update status
    inv.final_status = InvestigationStatus.REPRODUCED
    inv.duration_sec = 12.5
    db.save_investigation(inv)

    updated = db.get_investigation("test-inv-1")
    assert updated.final_status == InvestigationStatus.REPRODUCED
    assert updated.duration_sec == 12.5


def test_db_claims_and_refs(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    ref = SourceRef(path="click/core.py", start_line=50, end_line=55, snippet="pass", verified=True)
    claim = Claim(
        investigation_id="inv-claims",
        kind=ClaimKind.SOURCE_EVIDENCE,
        text="Line 50 defines Command",
        status=ClaimStatus.VERIFIED,
        confidence="high",
        source_ref=ref,
    )
    db.save_claim(claim)

    claims = db.list_claims("inv-claims")
    assert len(claims) == 1
    assert claims[0].kind == ClaimKind.SOURCE_EVIDENCE
    assert claims[0].source_ref is not None
    assert claims[0].source_ref.path == "click/core.py"
    assert claims[0].source_ref.verified is True


def test_db_attempts(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    att = Attempt(
        investigation_id="inv-att",
        attempt_no=1,
        test_source="def test_sample(): assert 1 == 1",
        status=InvestigationStatus.REPRODUCED,
        exit_code=1,
        stdout="FAIL",
        stderr="",
        duration_sec=0.8,
        execution_origin=ExecutionOrigin.LIVE,
    )
    db.save_attempt(att)

    attempts = db.list_attempts("inv-att")
    assert len(attempts) == 1
    assert attempts[0].attempt_no == 1
    assert attempts[0].execution_origin == ExecutionOrigin.LIVE


def test_db_llm_cache(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    key = "hash-12345"
    assert db.get_cached_llm(key) is None

    payload = {"result": "ok", "value": 42}
    db.set_cached_llm(key, payload)

    cached = db.get_cached_llm(key)
    assert cached == payload
