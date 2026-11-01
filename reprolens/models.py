"""Core Pydantic models and Enums for ReproLens."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ExecutionOrigin(str, Enum):
    LIVE = "live"
    RECORDED = "recorded"


class ExecutionMode(str, Enum):
    DOCKER = "docker"
    REMOTE = "remote"
    DEMO = "demo"


class InvestigationStatus(str, Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    REPRODUCING = "REPRODUCING"
    REPRODUCED = "REPRODUCED"
    PATCH_VALIDATED = "PATCH_VALIDATED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    INVALID_TEST = "INVALID_TEST"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"


class ClaimKind(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    SOURCE_EVIDENCE = "SOURCE_EVIDENCE"
    EXECUTION_EVIDENCE = "EXECUTION_EVIDENCE"


class ClaimStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"


class ExpectedSymptom(BaseModel):
    """Specification of the failure expected in test reproduction."""

    exception_type: str = Field(
        ..., description="Fully qualified or standard exception class name, e.g. TypeError"
    )
    message_regex: str = Field(
        default="", description="Regex or substring that must match the exception message"
    )
    description: str = Field(default="", description="Human-readable description of symptom")
    target_symbols: list[str] = Field(
        default_factory=list, description="List of functions/classes in target repo being tested"
    )


class SourceRef(BaseModel):
    """A citation of a specific line range in the repository source."""

    path: str
    start_line: int
    end_line: int
    snippet: str = ""
    verified: bool = False


class Claim(BaseModel):
    """An assertion in the evidence ledger."""

    id: str | None = None
    investigation_id: str
    kind: ClaimKind
    text: str
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    confidence: str = "medium"  # low, medium, high
    source_ref: SourceRef | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class Attempt(BaseModel):
    """A test generation and execution attempt."""

    id: str | None = None
    investigation_id: str
    attempt_no: int
    test_source: str
    status: InvestigationStatus
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    execution_origin: ExecutionOrigin = ExecutionOrigin.LIVE
    created_at: datetime = Field(default_factory=_utc_now)


class GitHubIssue(BaseModel):
    """Normalized representation of an issue from GitHub or pasted text."""

    owner: str
    repo: str
    number: int | None = None
    url: str
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    created_at: str | None = None
    state: str = "open"
    author_association: str = "NONE"
    comments: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "api"  # "api" or "pasted"
    code_blocks: list[str] = Field(default_factory=list)
    tracebacks: list[str] = Field(default_factory=list)
    mentioned_files: list[str] = Field(default_factory=list)
    mentioned_symbols: list[str] = Field(default_factory=list)
    version_strings: list[str] = Field(default_factory=list)
    expected_vs_actual: str = ""


class Investigation(BaseModel):
    """Top-level record of an issue reproduction investigation."""

    id: str
    repo: str
    issue_number: int | None = None
    issue_url: str
    commit_sha: str = ""
    issue_summary: str = ""
    final_status: InvestigationStatus = InvestigationStatus.PENDING
    created_at: datetime = Field(default_factory=_utc_now)
    duration_sec: float = 0.0
    mode: ExecutionMode = ExecutionMode.DEMO


class PatchRecord(BaseModel):
    """Candidate patch diff and validation outcome."""

    id: str | None = None
    investigation_id: str
    diff: str
    status: InvestigationStatus
    baseline_passed: bool = False
    patched_passed: bool = False
    regression_clean: bool = False
    created_at: datetime = Field(default_factory=_utc_now)


class BisectRun(BaseModel):
    """Record of a git bisect execution step."""

    id: str | None = None
    investigation_id: str
    commit_sha: str
    status: str  # good, bad, skip, flaky
    run_count: int = 3
    pass_count: int = 0
    fail_count: int = 0
    created_at: datetime = Field(default_factory=_utc_now)


class LLMCall(BaseModel):
    """Audit log entry for an LLM API call."""

    id: str | None = None
    investigation_id: str | None = None
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    latency_sec: float = 0.0
    created_at: datetime = Field(default_factory=_utc_now)


class EvalRun(BaseModel):
    """Benchmark evaluation summary record."""

    id: str
    run_date: datetime = Field(default_factory=datetime.utcnow)
    model_id: str
    total_cases: int = 0
    reproduced_count: int = 0
    fail_to_pass_count: int = 0
    false_reproduction_count: int = 0
    invalid_test_count: int = 0
    env_error_count: int = 0
    reproduction_rate: float = 0.0
    fail_to_pass_rate: float = 0.0
    false_reproduction_rate: float = 0.0
    invalid_test_rate: float = 0.0
    env_error_rate: float = 0.0
    total_duration_sec: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float | None = None
