"""GitHub REST API Client and Issue Content Ingestion for ReproLens."""

import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from reprolens.config import Config
from reprolens.models import GitHubIssue

GITHUB_ISSUE_URL_PATTERN = re.compile(
    r"^(?:https?://github\.com/)?([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)(?:/issues/(\d+)|#(\d+))?/?$"
)

TRACEBACK_PATTERN = re.compile(
    r"(Traceback \(most recent call last\):[\s\S]*?(?:[A-Za-z_][A-Za-z0-9_]*Error|Exception):[^\n]+)",
    re.MULTILINE,
)

CODE_BLOCK_PATTERN = re.compile(r"```(?:[a-zA-Z0-9_\-]+)?\n([\s\S]*?)```")
PYTHON_FILE_PATTERN = re.compile(r"\b([a-zA-Z0-9_\-/\\]+\.py)\b")
VERSION_PATTERN = re.compile(
    r"\b(?:Python\s+)?(?:v)?(\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?)\b", re.IGNORECASE
)


def parse_issue_reference(ref_str: str) -> tuple[str, str, int | None]:
    """Parse a GitHub issue URL, repo URL, or owner/repo#n string.

    Returns: (owner, repo, issue_number)
    Raises: ValueError if the format is invalid.
    """
    clean_ref = ref_str.strip()
    match = GITHUB_ISSUE_URL_PATTERN.match(clean_ref)
    if not match:
        raise ValueError(
            f"Invalid GitHub reference: '{ref_str}'. "
            "Expected formats: 'https://github.com/owner/repo/issues/123', 'owner/repo#123', or 'owner/repo'."
        )

    owner, repo, num1, num2 = match.groups()
    num = int(num1 or num2) if (num1 or num2) else None
    return owner, repo, num


def extract_code_blocks(text: str) -> list[str]:
    """Extract code snippets enclosed in fenced code blocks."""
    if not text:
        return []
    return [match.strip() for match in CODE_BLOCK_PATTERN.findall(text) if match.strip()]


def extract_tracebacks(text: str) -> list[str]:
    """Extract full Python tracebacks from text."""
    if not text:
        return []
    return [match.strip() for match in TRACEBACK_PATTERN.findall(text)]


def extract_mentioned_files(text: str) -> list[str]:
    """Extract referenced Python file paths from text."""
    if not text:
        return []
    files = set(PYTHON_FILE_PATTERN.findall(text))
    # Filter out common noise
    return sorted(f for f in files if not f.startswith("test_repro_"))


def extract_mentioned_symbols(text: str) -> list[str]:
    """Extract likely class or function symbols mentioned in code blocks or backticks."""
    if not text:
        return []
    backticked = re.findall(r"`([a-zA-Z_][a-zA-Z0-9_\.]{2,})`", text)
    calls = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]+)\s*\(", text)
    symbols = set(backticked + calls)
    common_keywords = {
        "def",
        "class",
        "import",
        "from",
        "return",
        "self",
        "cls",
        "print",
        "str",
        "int",
        "dict",
        "list",
        "set",
        "tuple",
        "pytest",
        "assert",
        "true",
        "false",
        "none",
    }
    return sorted(s for s in symbols if s.lower() not in common_keywords and len(s) > 2)


def extract_version_strings(text: str) -> list[str]:
    """Extract mentioned Python or package version numbers."""
    if not text:
        return []
    versions = set(VERSION_PATTERN.findall(text))
    return sorted(versions)


def extract_expected_vs_actual(text: str) -> str:
    """Extract sections describing expected vs actual behavior."""
    if not text:
        return ""
    sections = []
    # Search for headings or bullet points mentioning expected/actual
    patterns = [
        r"(###?\s*Expected[\s\S]*?)(?=###?|$)",
        r"(###?\s*Actual[\s\S]*?)(?=###?|$)",
        r"(\*\*Expected\*\*[\s\S]*?)(?=\*\*Actual\*\*|\n\n|$)",
        r"(\*\*Actual\*\*[\s\S]*?)(?=\*\*Expected\*\*|\n\n|$)",
    ]
    for pat in patterns:
        for match in re.findall(pat, text, re.IGNORECASE):
            sections.append(match.strip())
    return "\n\n".join(sections)


class GitHubClient:
    """Client for interacting with GitHub REST API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or Config.GITHUB_TOKEN

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ReproLens/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request_with_retry(
        self, client: httpx.Client, url: str, max_retries: int = 3
    ) -> httpx.Response:
        """Execute HTTP request with exponential backoff for 5xx/network errors."""
        delay = 1.0
        for attempt in range(max_retries):
            try:
                resp = client.get(url, headers=self._get_headers())
                if resp.status_code == 404:
                    return resp
                if resp.status_code == 410:
                    return resp
                if resp.status_code in (403, 429):
                    return resp
                if resp.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return resp
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Network error communicating with GitHub API: {e}") from e
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("GitHub API request failed after retries.")

    def fetch_issue(
        self,
        ref: str,
        pasted_text: str | None = None,
        max_comments: int = 15,
        max_comment_chars: int = 15000,
    ) -> GitHubIssue:
        """Fetch and parse a GitHub issue or construct from pasted details."""
        owner, repo, number = parse_issue_reference(ref)

        # If pasted text is supplied and no number provided, treat as pasted issue
        if pasted_text and not number:
            code_blocks = extract_code_blocks(pasted_text)
            tracebacks = extract_tracebacks(pasted_text)
            mentioned_files = extract_mentioned_files(pasted_text)
            mentioned_symbols = extract_mentioned_symbols(pasted_text)
            version_strings = extract_version_strings(pasted_text)
            exp_vs_act = extract_expected_vs_actual(pasted_text)

            return GitHubIssue(
                owner=owner,
                repo=repo,
                number=None,
                url=f"https://github.com/{owner}/{repo}",
                title="Pasted Issue",
                body=pasted_text,
                labels=[],
                created_at=datetime.now(UTC).isoformat(),
                state="open",
                source="pasted",
                code_blocks=code_blocks,
                tracebacks=tracebacks,
                mentioned_files=mentioned_files,
                mentioned_symbols=mentioned_symbols,
                version_strings=version_strings,
                expected_vs_actual=exp_vs_act,
            )

        if not number:
            raise ValueError(
                f"No issue number provided in reference '{ref}'. "
                "Please specify an issue number (e.g. owner/repo#123)."
            )

        with httpx.Client(timeout=15.0) as client:
            issue_url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{number}"
            resp = self._request_with_retry(client, issue_url)

            if resp.status_code == 404:
                raise ValueError(
                    f"Repository or issue '{owner}/{repo}#{number}' not found (404). "
                    "Note that private repositories are not supported unless a GITHUB_TOKEN "
                    "with authorized access permissions is configured."
                )

            if resp.status_code == 410:
                raise ValueError(f"Issue '{owner}/{repo}#{number}' has been deleted (410).")

            if resp.status_code in (403, 429):
                remaining = resp.headers.get("X-RateLimit-Remaining", "0")
                reset_ts = resp.headers.get("X-RateLimit-Reset", "")
                reset_time_str = ""
                if reset_ts and reset_ts.isdigit():
                    reset_dt = datetime.fromtimestamp(int(reset_ts), tz=UTC)
                    reset_time_str = f" Rate limit resets at: {reset_dt.strftime('%H:%M:%S UTC')}."
                raise RuntimeError(
                    f"GitHub API rate limit exceeded (Remaining: {remaining}).{reset_time_str} "
                    "Configure GITHUB_TOKEN in .env to increase rate limits to 5,000 req/hr."
                )

            resp.raise_for_status()
            data = resp.json()

            # Reject Pull Requests
            if "pull_request" in data:
                raise ValueError(
                    f"Reference '{owner}/{repo}#{number}' is a Pull Request, not an Issue. "
                    "ReproLens specifically reproduces bug issues."
                )

            title = data.get("title", "")
            body = data.get("body") or ""
            labels = [
                lbl["name"]
                for lbl in data.get("labels", [])
                if isinstance(lbl, dict) and "name" in lbl
            ]
            created_at = data.get("created_at")
            state = data.get("state", "open")
            author_association = data.get("author_association", "NONE")

            # Fetch and score comments
            comments: list[dict[str, Any]] = []
            if data.get("comments", 0) > 0:
                comments_url = data.get("comments_url")
                if comments_url:
                    c_resp = self._request_with_retry(client, f"{comments_url}?per_page=30")
                    if c_resp.status_code == 200:
                        raw_comments = c_resp.json()
                        scored_comments = []
                        for c in raw_comments:
                            c_body = c.get("body") or ""
                            author_assoc = c.get("author_association", "NONE")
                            score = 0
                            if author_assoc in ("OWNER", "MEMBER", "COLLABORATOR"):
                                score += 3
                            if "```" in c_body:
                                score += 2
                            if "Traceback" in c_body:
                                score += 3
                            scored_comments.append((score, c))

                        # Sort highest score first, up to max_comments
                        scored_comments.sort(key=lambda x: x[0], reverse=True)
                        total_chars = 0
                        for _, c in scored_comments[:max_comments]:
                            c_body = c.get("body") or ""
                            if total_chars + len(c_body) > max_comment_chars:
                                c_body = (
                                    c_body[: max_comment_chars - total_chars] + "... [truncated]"
                                )
                            comments.append(
                                {
                                    "id": c.get("id"),
                                    "user": c.get("user", {}).get("login", ""),
                                    "author_association": c.get("author_association", "NONE"),
                                    "created_at": c.get("created_at"),
                                    "body": c_body,
                                }
                            )
                            total_chars += len(c_body)
                            if total_chars >= max_comment_chars:
                                break

            # Aggregate all text for parsing
            all_text = body + "\n\n" + "\n\n".join(c["body"] for c in comments)
            if pasted_text:
                all_text = pasted_text + "\n\n" + all_text

            code_blocks = extract_code_blocks(all_text)
            tracebacks = extract_tracebacks(all_text)
            mentioned_files = extract_mentioned_files(all_text)
            mentioned_symbols = extract_mentioned_symbols(all_text)
            version_strings = extract_version_strings(all_text)
            exp_vs_act = extract_expected_vs_actual(all_text)

            return GitHubIssue(
                owner=owner,
                repo=repo,
                number=number,
                url=data.get("html_url", f"https://github.com/{owner}/{repo}/issues/{number}"),
                title=title,
                body=body,
                labels=labels,
                created_at=created_at,
                state=state,
                author_association=author_association,
                comments=comments,
                source="pasted" if pasted_text and not body else "api",
                code_blocks=code_blocks,
                tracebacks=tracebacks,
                mentioned_files=mentioned_files,
                mentioned_symbols=mentioned_symbols,
                version_strings=version_strings,
                expected_vs_actual=exp_vs_act,
            )
