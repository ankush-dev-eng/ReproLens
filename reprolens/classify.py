"""Execution output parser and strict multi-gate classification engine."""

import re
from dataclasses import dataclass

from reprolens.models import ExpectedSymptom, InvestigationStatus
from reprolens.sandbox.base import ExecutionResult


@dataclass
class ClassificationResult:
    """Detailed diagnosis and verdict for a test execution attempt."""

    status: InvestigationStatus
    reason: str
    extracted_exception_type: str | None = None
    extracted_message: str | None = None
    has_target_repo_frame: bool = False
    is_flaky: bool = False
    flaky_runs_summary: str = ""


PYTEST_FAILURE_SUMMARY_PATTERN = re.compile(
    r"^FAILED\s+[^\s]+::[^\s]+\s+-\s+([a-zA-Z_][a-zA-Z0-9_\.]*(?:Error|Exception|AssertionError))(?::\s*(.*))?$",
    re.MULTILINE,
)

PYTEST_E_LINE_PATTERN = re.compile(
    r"^E\s+([a-zA-Z_][a-zA-Z0-9_\.]*(?:Error|Exception|AssertionError))(?::\s*(.*))?$",
    re.MULTILINE,
)

STANDARD_EXC_PATTERN = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_\.]*(?:Error|Exception|Warning|Interrupt|Exit|AssertionError))(?::\s*(.*))?$",
    re.MULTILINE,
)

STANDARD_TRACEBACK_PATTERN = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\w+))?', re.IGNORECASE)

PYTEST_FRAME_PATTERN = re.compile(
    r"^([a-zA-Z0-9_\-/\\]+\.py):(\d+):\s+in\s+([a-zA-Z0-9_]+)",
    re.MULTILINE,
)


def extract_failure_exception(output_text: str) -> tuple[str | None, str | None]:
    """Parse output to extract the root raised exception class and message."""
    # 1. Prefer pytest summary failure line
    sum_matches = list(PYTEST_FAILURE_SUMMARY_PATTERN.finditer(output_text))
    if sum_matches:
        last = sum_matches[-1]
        return last.group(1).split(".")[-1], (last.group(2) or "").strip()

    # 2. Prefer pytest 'E ' error line
    e_matches = list(PYTEST_E_LINE_PATTERN.finditer(output_text))
    if e_matches:
        last = e_matches[-1]
        return last.group(1).split(".")[-1], (last.group(2) or "").strip()

    # 3. Standard exception line
    std_matches = list(STANDARD_EXC_PATTERN.finditer(output_text))
    if std_matches:
        last = std_matches[-1]
        return last.group(1).split(".")[-1], (last.group(2) or "").strip()

    return None, None


def has_frame_in_target_repo(
    output_text: str,
    test_filename: str = "test_repro",
    known_repo_files: set[str] | None = None,
) -> bool:
    """Check if the traceback contains at least one frame inside the target repository code."""
    frames: list[tuple[str, str]] = []

    for path_str, line_no, _ in STANDARD_TRACEBACK_PATTERN.findall(output_text):
        frames.append((path_str, line_no))

    for match in PYTEST_FRAME_PATTERN.finditer(output_text):
        frames.append((match.group(1), match.group(2)))

    if not frames:
        return False

    for path_str, _ in frames:
        norm_path = path_str.replace("\\", "/")
        # Ignore frames inside the test script itself
        if test_filename in norm_path or "test_repro" in norm_path:
            continue
        # Ignore python stdlib and virtualenv/site-packages
        if any(
            ignored in norm_path
            for ignored in ("lib/python", "site-packages", "dist-packages", "pytest", "_pytest")
        ):
            continue

        # If known_repo_files is provided, verify matching file
        if known_repo_files:
            for f in known_repo_files:
                norm_f = f.replace("\\", "/")
                if (
                    norm_path == norm_f
                    or norm_f.endswith(norm_path)
                    or norm_path.endswith(norm_f)
                    or norm_path.split("/")[-1] == norm_f.split("/")[-1]
                ):
                    return True
        else:
            # Without explicit file list, non-stdlib/non-test frame is considered repo code
            return True

    return False


def classify_single_execution(
    result: ExecutionResult,
    expected_symptom: ExpectedSymptom,
    test_filename: str = "test_repro",
    known_repo_files: set[str] | None = None,
) -> ClassificationResult:
    """Classify a single pytest execution result against the expected symptom."""
    # 1. Check for wall-clock timeout
    if result.is_timeout or result.exit_code == 124:
        return ClassificationResult(
            status=InvestigationStatus.EXECUTION_TIMEOUT,
            reason=f"Execution exceeded wall-clock limit of {result.timed_out_after_sec or 60} seconds.",
        )

    all_output = f"{result.stdout}\n{result.stderr}"

    # 2. Check for environment / missing dependency errors
    if "ModuleNotFoundError:" in all_output:
        match = re.search(r"ModuleNotFoundError:\s*No module named '([^']+)'", all_output)
        missing_pkg = match.group(1) if match else "unknown"
        # If the missing module is not a local repo file, it is an environment failure
        if not known_repo_files or not any(missing_pkg in f for f in known_repo_files):
            return ClassificationResult(
                status=InvestigationStatus.ENVIRONMENT_ERROR,
                reason=f"Third-party dependency missing from sandbox environment: '{missing_pkg}'.",
                extracted_exception_type="ModuleNotFoundError",
                extracted_message=missing_pkg,
            )

    # 3. Check for pytest collection or syntax errors
    if "ERROR collecting" in all_output or "SyntaxError:" in all_output:
        exc_type, exc_msg = extract_failure_exception(all_output)
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason=f"Pytest collection or syntax error in test code: {exc_msg or 'Failed to collect test'}.",
            extracted_exception_type=exc_type or "CollectionError",
            extracted_message=exc_msg,
        )

    # 4. Check for pytest skip / xfail
    if " 1 skipped" in all_output or " 1 xfailed" in all_output:
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason="Test skipped or xfailed itself (prohibited by test guard policy).",
        )

    # 5. Check if test passed on buggy revision
    if result.exit_code == 0 and (" 1 passed" in all_output or "passed in" in all_output):
        return ClassificationResult(
            status=InvestigationStatus.NOT_REPRODUCED,
            reason="Test passed on the buggy revision. The reported bug could not be reproduced.",
        )

    # 6. Extract failure exception
    exc_type, exc_msg = extract_failure_exception(all_output)
    if not exc_type:
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason=f"Pytest failed with exit code {result.exit_code} but no exception could be identified.",
        )

    # Check for target repo frame in traceback
    has_repo_frame = has_frame_in_target_repo(all_output, test_filename, known_repo_files)

    # 7. Check exception type match
    expected_type = expected_symptom.exception_type.split(".")[-1]
    if exc_type != expected_type:
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason=f"Observed exception '{exc_type}' does not match expected symptom '{expected_type}'.",
            extracted_exception_type=exc_type,
            extracted_message=exc_msg,
            has_target_repo_frame=has_repo_frame,
        )

    # 8. Check message regex match if specified
    if (
        expected_symptom.message_regex
        and expected_symptom.message_regex.strip()
        and (not exc_msg or not re.search(expected_symptom.message_regex, exc_msg, re.IGNORECASE))
    ):
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason=(
                f"Observed exception message '{exc_msg}' does not match "
                f"expected regex '{expected_symptom.message_regex}'."
            ),
            extracted_exception_type=exc_type,
            extracted_message=exc_msg,
            has_target_repo_frame=has_repo_frame,
        )

    # 9. Verify traceback involves repository source
    if not has_repo_frame:
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason=(
                "Failure occurred exclusively inside test harness / stdlib without executing "
                "repository source code (unconditional assert or test setup failure)."
            ),
            extracted_exception_type=exc_type,
            extracted_message=exc_msg,
            has_target_repo_frame=False,
        )

    # Candidate single reproduction
    return ClassificationResult(
        status=InvestigationStatus.REPRODUCED,
        reason=f"Test failed with expected symptom '{exc_type}: {exc_msg}' inside target repository code.",
        extracted_exception_type=exc_type,
        extracted_message=exc_msg,
        has_target_repo_frame=True,
    )


def classify_multi_execution(
    results: list[ExecutionResult],
    expected_symptom: ExpectedSymptom,
    test_filename: str = "test_repro",
    known_repo_files: set[str] | None = None,
) -> ClassificationResult:
    """Perform 3-run consistency check to confirm deterministic reproduction (reject flaky tests)."""
    if not results:
        return ClassificationResult(
            status=InvestigationStatus.INVALID_TEST,
            reason="No execution results provided for classification.",
        )

    statuses: list[ClassificationResult] = [
        classify_single_execution(r, expected_symptom, test_filename, known_repo_files)
        for r in results
    ]

    all_reproduced = all(s.status == InvestigationStatus.REPRODUCED for s in statuses)

    if all_reproduced:
        return statuses[0]

    # If all returned the exact same non-reproduced status
    first_status = statuses[0].status
    if all(s.status == first_status for s in statuses):
        return statuses[0]

    # Inconsistent / Flaky test
    summary_parts = [f"Run {i + 1}: {s.status.value} ({s.reason})" for i, s in enumerate(statuses)]
    return ClassificationResult(
        status=InvestigationStatus.INVALID_TEST,
        reason=f"Test is flaky or non-deterministic across {len(results)} executions.",
        is_flaky=True,
        flaky_runs_summary=" | ".join(summary_parts),
    )
