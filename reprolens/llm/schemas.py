"""Pydantic schemas for structured LLM interactions."""

from typing import Literal

from pydantic import BaseModel, Field

from reprolens.models import ExpectedSymptom


class IssueUnderstandingSchema(BaseModel):
    """Schema for stage 1: issue analysis and symptom extraction."""

    expected_behavior: str = Field(..., description="What the reporter expected to happen")
    actual_behavior: str = Field(..., description="What actually occurred (error/incorrect output)")
    symptom_statement: str = Field(..., description="Precise summary of the bug manifestation")
    candidate_symbols: list[str] = Field(
        default_factory=list,
        description="Repository classes, functions, or modules likely involved",
    )
    missing_information: str = Field(
        default="",
        description="Clarifications or environment details missing from the issue report",
    )
    is_reproducible_theoretically: bool = Field(
        default=True,
        description="Whether the report contains sufficient information to attempt reproduction",
    )


class RootCauseHypothesis(BaseModel):
    """A candidate hypothesis for the bug's root cause."""

    rank: int = Field(..., description="Ranking from 1 (most likely) to N")
    hypothesis_text: str = Field(..., description="Explanation of why the bug occurs")
    confidence: Literal["low", "medium", "high"] = Field(
        default="medium", description="Confidence level in this hypothesis"
    )
    file_path: str = Field(..., description="Exact file path relative to repository root")
    start_line: int = Field(..., description="Start line number in the file")
    end_line: int = Field(..., description="End line number in the file")
    snippet: str = Field(
        default="", description="Exact code snippet corresponding to the cited lines"
    )


class RootCauseInvestigationSchema(BaseModel):
    """Schema for stage 2: root cause hypotheses and source citations."""

    summary: str = Field(..., description="Overview of the investigation findings")
    hypotheses: list[RootCauseHypothesis] = Field(
        default_factory=list, description="Ranked candidate hypotheses"
    )


class ReproTestGenerationSchema(BaseModel):
    """Schema for stage 3: minimal reproduction test creation."""

    thought_process: str = Field(..., description="Brief reasoning about the reproduction strategy")
    expected_symptom: ExpectedSymptom = Field(
        ..., description="The exact failure symptom expected when running the test"
    )
    test_code: str = Field(
        ...,
        description="Complete Python code for test_repro_issue_<n>.py including EXPECTED_SYMPTOM dict and test function",
    )


class TestRepairSchema(BaseModel):
    """Schema for stage 4: targeted test repair after execution observation."""

    repair_diagnosis: str = Field(
        ..., description="Explanation of why previous attempt failed and what is repaired"
    )
    expected_symptom: ExpectedSymptom = Field(
        ...,
        description="The expected failure symptom (MUST remain identical to original attempt)",
    )
    repaired_test_code: str = Field(
        ...,
        description="Updated complete test_repro_issue_<n>.py Python code",
    )


class PatchGenerationSchema(BaseModel):
    """Schema for stage 5: candidate patch generation."""

    explanation: str = Field(
        ..., description="Explanation of how the patch addresses the root cause"
    )
    target_file: str = Field(..., description="Relative path of file to be modified")
    diff: str = Field(..., description="Unified diff that can be applied with git apply")
