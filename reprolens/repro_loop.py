"""Reproduction loop: Generate -> Validate -> Execute -> Observe -> Repair -> Re-execute."""

from pathlib import Path

from reprolens.classify import (
    ClassificationResult,
    classify_multi_execution,
    classify_single_execution,
)
from reprolens.config import Config
from reprolens.ledger import EvidenceLedger
from reprolens.llm.client import OpenRouterClient
from reprolens.llm.prompts import (
    REPRO_TEST_GENERATION_PROMPT,
    SYSTEM_SECURITY_PROMPT,
    TEST_REPAIR_PROMPT,
)
from reprolens.llm.schemas import (
    IssueUnderstandingSchema,
    ReproTestGenerationSchema,
    RootCauseInvestigationSchema,
    TestRepairSchema,
)
from reprolens.models import (
    Attempt,
    ExpectedSymptom,
    GitHubIssue,
    InvestigationStatus,
)
from reprolens.retrieval import CodeExcerpt
from reprolens.sandbox.base import ExecutionBackend
from reprolens.test_guard import validate_repair_attempt, validate_test_code

MAX_OUTPUT_CHARS = 65536  # 64 KB output truncation limit


def truncate_output(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate output at max_chars with a clear marker."""
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + f"\n... [TRUNCATED AT {max_chars} BYTES] ..."


class ReproductionEngine:
    """Orchestrates test generation, sandboxed execution, and multi-attempt repair."""

    def __init__(
        self,
        backend: ExecutionBackend,
        llm: OpenRouterClient,
        ledger: EvidenceLedger,
        max_repairs: int = 3,
    ) -> None:
        self.backend = backend
        self.llm = llm
        self.ledger = ledger
        self.max_repairs = max_repairs

    def run_loop(
        self,
        investigation_id: str,
        repo_dir: Path,
        issue: GitHubIssue,
        code_excerpts: list[CodeExcerpt],
        understanding: IssueUnderstandingSchema,
        root_causes: RootCauseInvestigationSchema,
        known_repo_files: set[str] | None = None,
    ) -> tuple[InvestigationStatus, list[Attempt]]:
        """Run up to 3 repair attempts to create a verified, deterministic reproduction test."""
        attempts: list[Attempt] = []
        test_filename = f"test_repro_issue_{issue.number or 'pasted'}.py"

        # Format retrieved excerpts for LLM prompt
        formatted_excerpts = "\n\n".join(
            f"--- {exc.path} (lines {exc.start_line}-{exc.end_line}) ---\n{exc.content}"
            for exc in code_excerpts[:6]
        )

        # 1. Generate initial test
        gen_prompt = REPRO_TEST_GENERATION_PROMPT.format(
            repo=f"{issue.owner}/{issue.repo}",
            issue_number=issue.number or 1,
            symptom_statement=understanding.symptom_statement,
            candidate_symbols=", ".join(understanding.candidate_symbols) or "None",
            code_excerpts=formatted_excerpts,
        )

        gen_resp: ReproTestGenerationSchema = self.llm.generate_structured(
            system_prompt=SYSTEM_SECURITY_PROMPT,
            user_prompt=gen_prompt,
            schema=ReproTestGenerationSchema,
            investigation_id=investigation_id,
        )

        current_test_code = gen_resp.test_code
        original_symptom: ExpectedSymptom = gen_resp.expected_symptom
        attempt_no = 0

        while attempt_no <= self.max_repairs:
            attempt_no += 1

            # Validate with static test guard
            guard_res = validate_test_code(
                current_test_code,
                expected_target_symbols=original_symptom.target_symbols,
            )

            if not guard_res.passed:
                # Guard failed
                attempt = self.ledger.record_attempt_and_execution_evidence(
                    investigation_id=investigation_id,
                    attempt_no=attempt_no,
                    test_source=current_test_code,
                    status=InvestigationStatus.INVALID_TEST,
                    exit_code=1,
                    stdout="",
                    stderr=f"Static Guard Failure: {guard_res.reason}",
                    duration_sec=0.01,
                    execution_origin=self.backend.mode.value,
                )
                attempts.append(attempt)

                if attempt_no > self.max_repairs:
                    break

                # Attempt repair
                current_test_code = self._repair_test(
                    issue=issue,
                    attempt_no=attempt_no,
                    previous_test=current_test_code,
                    exit_code=1,
                    observed_status=InvestigationStatus.INVALID_TEST,
                    stdout="",
                    stderr=guard_res.reason,
                    code_excerpts=formatted_excerpts,
                    original_symptom=original_symptom,
                    investigation_id=investigation_id,
                )
                continue

            # Execute test in sandbox backend
            exec_res = self.backend.execute(
                test_source=current_test_code,
                repo_dir=repo_dir,
                test_filename=test_filename,
                timeout_sec=Config.EXECUTION_TIMEOUT_SEC,
            )

            stdout_trunc = truncate_output(exec_res.stdout)
            stderr_trunc = truncate_output(exec_res.stderr)

            # Classify initial execution
            initial_cls: ClassificationResult = classify_single_execution(
                result=exec_res,
                expected_symptom=original_symptom,
                test_filename=test_filename,
                known_repo_files=known_repo_files,
            )

            if initial_cls.status == InvestigationStatus.REPRODUCED:
                # Run 2 additional executions to verify consistency across 3 total runs
                run_2 = self.backend.execute(
                    test_source=current_test_code,
                    repo_dir=repo_dir,
                    test_filename=test_filename,
                    timeout_sec=Config.EXECUTION_TIMEOUT_SEC,
                )
                run_3 = self.backend.execute(
                    test_source=current_test_code,
                    repo_dir=repo_dir,
                    test_filename=test_filename,
                    timeout_sec=Config.EXECUTION_TIMEOUT_SEC,
                )

                multi_cls = classify_multi_execution(
                    results=[exec_res, run_2, run_3],
                    expected_symptom=original_symptom,
                    test_filename=test_filename,
                    known_repo_files=known_repo_files,
                )

                attempt = self.ledger.record_attempt_and_execution_evidence(
                    investigation_id=investigation_id,
                    attempt_no=attempt_no,
                    test_source=current_test_code,
                    status=multi_cls.status,
                    exit_code=exec_res.exit_code,
                    stdout=stdout_trunc,
                    stderr=stderr_trunc,
                    duration_sec=exec_res.duration_sec,
                    execution_origin=exec_res.execution_origin,
                )
                attempts.append(attempt)

                if multi_cls.status == InvestigationStatus.REPRODUCED:
                    # Promoted hypotheses in ledger!
                    self.ledger.promote_hypotheses_on_reproduction(investigation_id, multi_cls)
                    return InvestigationStatus.REPRODUCED, attempts

            else:
                # Not reproduced / Invalid / Environment error
                attempt = self.ledger.record_attempt_and_execution_evidence(
                    investigation_id=investigation_id,
                    attempt_no=attempt_no,
                    test_source=current_test_code,
                    status=initial_cls.status,
                    exit_code=exec_res.exit_code,
                    stdout=stdout_trunc,
                    stderr=stderr_trunc,
                    duration_sec=exec_res.duration_sec,
                    execution_origin=exec_res.execution_origin,
                )
                attempts.append(attempt)

                # If missing environment dependency or wall-clock timeout, do not endlessly repair
                if initial_cls.status in (
                    InvestigationStatus.ENVIRONMENT_ERROR,
                    InvestigationStatus.EXECUTION_TIMEOUT,
                ):
                    return initial_cls.status, attempts

            # Trigger repair if attempts remain
            if attempt_no <= self.max_repairs:
                repaired_code = self._repair_test(
                    issue=issue,
                    attempt_no=attempt_no,
                    previous_test=current_test_code,
                    exit_code=exec_res.exit_code,
                    observed_status=initial_cls.status,
                    stdout=stdout_trunc,
                    stderr=stderr_trunc,
                    code_excerpts=formatted_excerpts,
                    original_symptom=original_symptom,
                    investigation_id=investigation_id,
                )

                # Validate repair against programmatic rules (no assertion weakening)
                valid, reason = validate_repair_attempt(current_test_code, repaired_code)
                if valid:
                    current_test_code = repaired_code

        final_status = attempts[-1].status if attempts else InvestigationStatus.NOT_REPRODUCED
        return final_status, attempts

    def _repair_test(
        self,
        issue: GitHubIssue,
        attempt_no: int,
        previous_test: str,
        exit_code: int,
        observed_status: InvestigationStatus,
        stdout: str,
        stderr: str,
        code_excerpts: str,
        original_symptom: ExpectedSymptom,
        investigation_id: str,
    ) -> str:
        """Query LLM for a repaired test satisfying EXPECTED_SYMPTOM."""
        repair_prompt = TEST_REPAIR_PROMPT.format(
            symptom_statement=original_symptom.description or original_symptom.exception_type,
            attempt_no=attempt_no,
            previous_test_code=previous_test,
            exit_code=exit_code,
            observed_status=observed_status.value,
            stdout=stdout[:4000],
            stderr=stderr[:4000],
            code_excerpts=code_excerpts,
            expected_symptom_json=original_symptom.model_dump_json(),
        )

        try:
            resp: TestRepairSchema = self.llm.generate_structured(
                system_prompt=SYSTEM_SECURITY_PROMPT,
                user_prompt=repair_prompt,
                schema=TestRepairSchema,
                investigation_id=investigation_id,
            )
            return resp.repaired_test_code
        except Exception:
            return previous_test
