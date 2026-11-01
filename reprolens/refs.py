"""Source reference verification against repository files at target commit SHA."""

import re
from pathlib import Path

from reprolens.models import SourceRef


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace by collapsing consecutive spaces, tabs, and newlines."""
    return re.sub(r"\s+", " ", text).strip()


def verify_source_ref(repo_dir: Path, ref: SourceRef) -> SourceRef:
    """Verify that a source reference accurately points to real code in the repository.

    Rules:
    1. File path must exist and be a regular file inside repo_dir.
    2. Start and end lines must be within 1 and total_file_lines.
    3. start_line <= end_line.
    4. If snippet is provided, its whitespace-normalized text must match the lines.
    """
    target_file = (repo_dir / ref.path).resolve()

    # Path traversal check: must stay within repo_dir
    try:
        target_file.relative_to(repo_dir.resolve())
    except ValueError:
        ref.verified = False
        return ref

    if not target_file.exists() or not target_file.is_file():
        ref.verified = False
        return ref

    try:
        lines = target_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        ref.verified = False
        return ref

    total_lines = len(lines)
    if ref.start_line < 1 or ref.start_line > total_lines:
        ref.verified = False
        return ref

    if ref.end_line < ref.start_line or ref.end_line > total_lines:
        ref.verified = False
        return ref

    # If snippet was provided, check whitespace-normalized content match
    if ref.snippet and ref.snippet.strip():
        extracted_text = "\n".join(lines[ref.start_line - 1 : ref.end_line])
        norm_snippet = normalize_whitespace(ref.snippet)
        norm_extracted = normalize_whitespace(extracted_text)

        # Match if snippet is contained in or equals the extracted region
        if norm_snippet not in norm_extracted and norm_extracted not in norm_snippet:
            ref.verified = False
            return ref

    # All checks passed
    ref.verified = True
    return ref
