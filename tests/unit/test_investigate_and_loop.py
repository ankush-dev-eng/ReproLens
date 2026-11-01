"""Tests for Reproduction Loop and Investigation Orchestrator."""

from reprolens.classify import ClassificationResult
from reprolens.db import Database
from reprolens.ledger import EvidenceLedger
from reprolens.llm.client import FakeLLM
from reprolens.models import (
    ClaimStatus,
    ExecutionMode,
    ExecutionOrigin,
    GitHubIssue,
    InvestigationStatus,
    SourceRef,
)
from reprolens.repro_loop import ReproductionEngine, truncate_output
from reprolens.sandbox.base import ExecutionBackend, ExecutionResult


class MockBackend(ExecutionBackend):
    def __init__(self, exit_code: int = 1, stdout: str = "", stderr: str = ""):
        self._exit_code = exit_code
        self._stdout = stdout
        self._stderr = stderr
        self.call_count = 0

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.DOCKER

    def execute(
        self, test_source, repo_dir, test_filename="test_repro.py", timeout_sec=60, env_vars=None
    ):
        self.call_count += 1
        return ExecutionResult(
            exit_code=self._exit_code,
            stdout=self._stdout,
            stderr=self._stderr,
            duration_sec=0.1,
            execution_origin=ExecutionOrigin.LIVE,
        )


def test_truncate_output():
    short_text = "abc"
    assert truncate_output(short_text, 10) == "abc"

    long_text = "x" * 100
    res = truncate_output(long_text, 50)
    assert len(res) > 50
    assert "TRUNCATED" in res


def test_ledger_promotion(tmp_path):
    db = Database(tmp_path / "test_ledger.db")
    ledger = EvidenceLedger(db)

    ref = SourceRef(path="pkg/core.py", start_line=1, end_line=5, verified=True)
    hyp = ledger.record_hypothesis("inv-1", "Bug is in pkg/core.py line 2", source_ref=ref)
    assert hyp.status == ClaimStatus.UNVERIFIED

    cls_res = ClassificationResult(
        status=InvestigationStatus.REPRODUCED,
        reason="Reproduced with expected exception",
    )
    promoted = ledger.promote_hypotheses_on_reproduction("inv-1", cls_res)
    assert promoted == 1

    claims = db.list_claims("inv-1")
    assert claims[0].status == ClaimStatus.VERIFIED


def test_reproduction_engine_success_clean(tmp_path):
    db = Database(tmp_path / "test_repro.db")
    ledger = EvidenceLedger(db)

    # Output that triggers REPRODUCED
    valid_test_output = """
============================= test session starts =============================
Traceback (most recent call last):
  File "pkg/core.py", line 22, in execute
    raise ValueError("invalid operand")
ValueError: invalid operand
============================== 1 failed in 0.1s ===============================
"""
    backend = MockBackend(exit_code=1, stdout=valid_test_output)

    fake_llm = FakeLLM()
    gen_payload = {
        "thought_process": "Generate test calling execute",
        "expected_symptom": {
            "exception_type": "ValueError",
            "message_regex": "invalid operand",
            "target_symbols": ["pkg.core.execute"],
        },
        "test_code": """
import pytest

EXPECTED_SYMPTOM = {
    "exception_type": "ValueError",
    "message_regex": "invalid operand",
    "target_symbols": ["pkg.core.execute"]
}

def test_reproduce_issue():
    from pkg.core import execute
    execute()
""",
    }
    fake_llm.set_response("Create a minimal", gen_payload)

    engine = ReproductionEngine(backend, fake_llm, ledger, max_repairs=1)

    issue = GitHubIssue(
        owner="owner",
        repo="repo",
        number=1,
        url="https://github.com/owner/repo/issues/1",
        title="Bug in execute",
        body="Raises ValueError",
    )
    from reprolens.llm.schemas import (
        IssueUnderstandingSchema,
        RootCauseHypothesis,
        RootCauseInvestigationSchema,
    )

    und = IssueUnderstandingSchema(
        expected_behavior="Runs ok",
        actual_behavior="Fails with ValueError",
        symptom_statement="ValueError: invalid operand",
        candidate_symbols=["pkg.core.execute"],
    )
    rc = RootCauseInvestigationSchema(
        summary="Root cause analysis",
        hypotheses=[
            RootCauseHypothesis(
                rank=1,
                hypothesis_text="Check failed",
                confidence="high",
                file_path="pkg/core.py",
                start_line=20,
                end_line=25,
            )
        ],
    )

    status, attempts = engine.run_loop(
        investigation_id="inv-loop",
        repo_dir=tmp_path,
        issue=issue,
        code_excerpts=[],
        understanding=und,
        root_causes=rc,
        known_repo_files={"pkg/core.py"},
    )

    assert status == InvestigationStatus.REPRODUCED
    # Verified consistency across 3 executions
    assert backend.call_count == 3
    assert len(attempts) == 1
    assert attempts[0].status == InvestigationStatus.REPRODUCED
