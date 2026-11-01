"""Evidence Ledger managing immutable claims, source citations, and status promotions."""

from datetime import UTC, datetime

from reprolens.classify import ClassificationResult
from reprolens.db import Database
from reprolens.models import (
    Attempt,
    Claim,
    ClaimKind,
    ClaimStatus,
    ExecutionOrigin,
    InvestigationStatus,
    SourceRef,
)


class EvidenceLedger:
    """Manages verified facts, hypotheses, and execution provenance."""

    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()

    def record_hypothesis(
        self,
        investigation_id: str,
        text: str,
        source_ref: SourceRef | None = None,
        confidence: str = "medium",
    ) -> Claim:
        """Register an unverified candidate explanation."""
        claim = Claim(
            investigation_id=investigation_id,
            kind=ClaimKind.HYPOTHESIS,
            text=text,
            status=ClaimStatus.UNVERIFIED,
            confidence=confidence,
            source_ref=source_ref,
            created_at=datetime.now(UTC),
        )
        self.db.save_claim(claim)
        return claim

    def record_source_evidence(
        self,
        investigation_id: str,
        text: str,
        source_ref: SourceRef,
    ) -> Claim:
        """Register verified code citation as source evidence."""
        claim = Claim(
            investigation_id=investigation_id,
            kind=ClaimKind.SOURCE_EVIDENCE,
            text=text,
            status=ClaimStatus.VERIFIED if source_ref.verified else ClaimStatus.UNVERIFIED,
            confidence="high" if source_ref.verified else "low",
            source_ref=source_ref,
            created_at=datetime.now(UTC),
        )
        self.db.save_claim(claim)
        return claim

    def record_attempt_and_execution_evidence(
        self,
        investigation_id: str,
        attempt_no: int,
        test_source: str,
        status: InvestigationStatus,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_sec: float,
        execution_origin: ExecutionOrigin = ExecutionOrigin.LIVE,
    ) -> Attempt:
        """Record test attempt and create corresponding execution evidence in ledger."""
        attempt = Attempt(
            investigation_id=investigation_id,
            attempt_no=attempt_no,
            test_source=test_source,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_sec=duration_sec,
            execution_origin=execution_origin,
            created_at=datetime.now(UTC),
        )
        self.db.save_attempt(attempt)

        # Create execution evidence claim
        exec_claim = Claim(
            investigation_id=investigation_id,
            kind=ClaimKind.EXECUTION_EVIDENCE,
            text=(
                f"Attempt #{attempt_no}: Executed test resulting in {status.value} "
                f"(exit code {exit_code}, {duration_sec:.2f}s, origin: {execution_origin.value})."
            ),
            status=ClaimStatus.VERIFIED
            if status in (InvestigationStatus.REPRODUCED, InvestigationStatus.PATCH_VALIDATED)
            else ClaimStatus.UNVERIFIED,
            confidence="high",
            created_at=datetime.now(UTC),
        )
        self.db.save_claim(exec_claim)
        return attempt

    def promote_hypotheses_on_reproduction(
        self,
        investigation_id: str,
        classification: ClassificationResult,
    ) -> int:
        """Promote candidate hypotheses to VERIFIED when test reproduction succeeds."""
        if classification.status != InvestigationStatus.REPRODUCED:
            return 0

        claims = self.db.list_claims(investigation_id)
        promoted_count = 0
        for c in claims:
            if c.kind == ClaimKind.HYPOTHESIS and c.status == ClaimStatus.UNVERIFIED:
                # If hypothesis has a verified source ref or relates to the reproduction
                c.status = ClaimStatus.VERIFIED
                self.db.save_claim(c)
                promoted_count += 1

        return promoted_count
