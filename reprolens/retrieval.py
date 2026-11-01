"""Targeted deterministic code retrieval for ReproLens without vector DBs or embeddings."""

import re
from dataclasses import dataclass
from pathlib import Path

from reprolens.indexer import RepoIndexer
from reprolens.models import GitHubIssue


@dataclass
class CodeExcerpt:
    """A bounded snippet of code with line numbers and retrieval provenance."""

    path: str
    start_line: int
    end_line: int
    content: str
    score: float
    reason: str


def extract_traceback_frames(traceback_text: str) -> list[tuple[str, int]]:
    """Extract (file_path, line_number) pairs from a Python traceback."""
    pattern = re.compile(r'File "([^"]+)", line (\d+)', re.IGNORECASE)
    frames = []
    for match in pattern.finditer(traceback_text):
        path_str, line_str = match.groups()
        try:
            line_no = int(line_str)
            # Normalize path
            norm_path = path_str.replace("\\", "/")
            frames.append((norm_path, line_no))
        except ValueError:
            continue
    return frames


def _read_line_window(file_path: Path, center_line: int, window: int = 30) -> tuple[int, int, str]:
    """Read lines around a target center line, returning (start_line, end_line, formatted_text)."""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return 1, 1, ""

    total = len(lines)
    start = max(1, center_line - window)
    end = min(total, center_line + window)

    excerpt_lines = []
    for i in range(start, end + 1):
        line_content = lines[i - 1]
        excerpt_lines.append(f"{i:4d} | {line_content}")

    return start, end, "\n".join(excerpt_lines)


def retrieve_relevant_code(
    repo_dir: Path,
    indexer: RepoIndexer,
    issue: GitHubIssue,
    max_chars: int = 40_000,
) -> list[CodeExcerpt]:
    """Deterministic, targeted retrieval prioritizing tracebacks and symbol citations."""
    excerpts: list[CodeExcerpt] = []
    seen_ranges: set[tuple[str, int, int]] = set()

    # 1. Traceback frames (Highest weight: 100.0)
    for tb in issue.tracebacks:
        frames = extract_traceback_frames(tb)
        for rel_candidate, line_no in frames:
            # Check if this frame exists in the repository
            for indexed_path in indexer.modules:
                if (
                    indexed_path == rel_candidate
                    or indexed_path.endswith("/" + rel_candidate)
                    or rel_candidate.endswith("/" + indexed_path)
                ):
                    full_file = repo_dir / indexed_path
                    if full_file.exists():
                        start, end, content = _read_line_window(full_file, line_no, window=25)
                        key = (indexed_path, start, end)
                        if key not in seen_ranges:
                            seen_ranges.add(key)
                            excerpts.append(
                                CodeExcerpt(
                                    path=indexed_path,
                                    start_line=start,
                                    end_line=end,
                                    content=content,
                                    score=100.0,
                                    reason=f"Traceback frame at line {line_no}",
                                )
                            )

    # 2. Mentioned files in issue text (Weight: 50.0)
    for mentioned_file in issue.mentioned_files:
        norm_mentioned = mentioned_file.replace("\\", "/")
        for indexed_path in indexer.modules:
            if (
                indexed_path == norm_mentioned
                or indexed_path.endswith("/" + norm_mentioned)
                or norm_mentioned.endswith(indexed_path)
            ):
                full_file = repo_dir / indexed_path
                if full_file.exists():
                    start, end, content = _read_line_window(full_file, 1, window=60)
                    key = (indexed_path, start, end)
                    if key not in seen_ranges:
                        seen_ranges.add(key)
                        excerpts.append(
                            CodeExcerpt(
                                path=indexed_path,
                                start_line=start,
                                end_line=end,
                                content=content,
                                score=50.0,
                                reason=f"File explicitly mentioned in issue ({mentioned_file})",
                            )
                        )

    # 3. Mentioned symbols (Weight: 30.0)
    for symbol in issue.mentioned_symbols:
        matches = indexer.find_symbol(symbol)
        for mod, sym_def in matches:
            full_file = repo_dir / mod.rel_path
            if full_file.exists():
                start = max(1, sym_def.start_line - 2)
                end = sym_def.end_line + 2
                start_l, end_l, content = _read_line_window(
                    full_file, (start + end) // 2, window=(end - start) // 2 + 5
                )
                key = (mod.rel_path, start_l, end_l)
                if key not in seen_ranges:
                    seen_ranges.add(key)
                    excerpts.append(
                        CodeExcerpt(
                            path=mod.rel_path,
                            start_line=start_l,
                            end_line=end_l,
                            content=content,
                            score=30.0,
                            reason=f"Symbol '{symbol}' defined in module",
                        )
                    )

    # 4. Keyword matching against module functions (Weight: 5.0 to 15.0)
    issue_keywords = set(re.findall(r"\b[a-zA-Z_]{4,}\b", (issue.title + " " + issue.body).lower()))
    for rel_path, mod in indexer.modules.items():
        score = 0.0
        matching_symbols = []
        for fn in mod.functions:
            fn_tokens = set(re.findall(r"\b[a-zA-Z_]{4,}\b", fn.name.lower()))
            overlap = issue_keywords.intersection(fn_tokens)
            if overlap:
                score += len(overlap) * 5.0
                matching_symbols.append(fn)

        if score > 0 and matching_symbols:
            top_fn = matching_symbols[0]
            full_file = repo_dir / rel_path
            start_l, end_l, content = _read_line_window(full_file, top_fn.start_line, window=20)
            key = (rel_path, start_l, end_l)
            if key not in seen_ranges:
                seen_ranges.add(key)
                excerpts.append(
                    CodeExcerpt(
                        path=rel_path,
                        start_line=start_l,
                        end_line=end_l,
                        content=content,
                        score=score,
                        reason=f"Function name matches issue keywords ({', '.join(fn.name for fn in matching_symbols[:2])})",
                    )
                )

    # Sort excerpts by score descending
    excerpts.sort(key=lambda x: x.score, reverse=True)

    # Trim to max_chars budget
    budgeted: list[CodeExcerpt] = []
    cur_chars = 0
    for exc in excerpts:
        if cur_chars + len(exc.content) > max_chars:
            remaining = max_chars - cur_chars
            if remaining > 500:
                truncated_content = exc.content[:remaining] + "\n... [truncated for budget]"
                budgeted.append(
                    CodeExcerpt(
                        path=exc.path,
                        start_line=exc.start_line,
                        end_line=exc.end_line,
                        content=truncated_content,
                        score=exc.score,
                        reason=exc.reason,
                    )
                )
            break
        budgeted.append(exc)
        cur_chars += len(exc.content)

    return budgeted
