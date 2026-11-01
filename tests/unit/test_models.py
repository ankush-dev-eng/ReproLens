"""Tests for core Pydantic models."""

from reprolens.models import (
    Attempt,
    Claim,
    ClaimKind,
    ClaimStatus,
    ExecutionMode,
    ExecutionOrigin,
    ExpectedSymptom,
    GitHubIssue,
    Investigation,
    InvestigationStatus,
    SourceRef,
)


def test_models_creation():
    symptom = ExpectedSymptom(
        exception_type="ValueError",
        message_regex="unexpected None",
        description="Fails when input is None",
        target_symbols=["pkg.mod.func"],
    )
    assert symptom.exception_type == "ValueError"

    ref = SourceRef(
        path="src/utils.py",
        start_line=10,
        end_line=20,
        snippet="def func(): pass",
        verified=True,
    )
    assert ref.verified is True

    claim = Claim(
        investigation_id="inv-123",
        kind=ClaimKind.HYPOTHESIS,
        text="Target function does not check for None",
        status=ClaimStatus.UNVERIFIED,
        confidence="high",
        source_ref=ref,
    )
    assert claim.kind == ClaimKind.HYPOTHESIS
    assert claim.source_ref.path == "src/utils.py"

    attempt = Attempt(
        investigation_id="inv-123",
        attempt_no=1,
        test_source="def test_foo(): pass",
        status=InvestigationStatus.REPRODUCED,
        exit_code=1,
        stdout="",
        stderr="ValueError: unexpected None",
        duration_sec=1.5,
        execution_origin=ExecutionOrigin.LIVE,
    )
    assert attempt.status == InvestigationStatus.REPRODUCED

    issue = GitHubIssue(
        owner="owner",
        repo="repo",
        number=42,
        url="https://github.com/owner/repo/issues/42",
        title="Bug in func",
        body="func(None) crashes with ValueError",
    )
    assert issue.number == 42
    assert issue.source == "api"

    inv = Investigation(
        id="inv-123",
        repo="owner/repo",
        issue_number=42,
        issue_url="https://github.com/owner/repo/issues/42",
        mode=ExecutionMode.DEMO,
    )
    assert inv.final_status == InvestigationStatus.PENDING
