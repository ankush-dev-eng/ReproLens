"""Tests for GitHub issue parsing and ingestion client."""

import httpx
import pytest

from reprolens.github_client import (
    GitHubClient,
    extract_code_blocks,
    extract_expected_vs_actual,
    extract_mentioned_files,
    extract_mentioned_symbols,
    extract_tracebacks,
    extract_version_strings,
    parse_issue_reference,
)


def test_parse_issue_reference():
    assert parse_issue_reference("https://github.com/psf/requests/issues/1234") == (
        "psf",
        "requests",
        1234,
    )
    assert parse_issue_reference("psf/requests#567") == ("psf", "requests", 567)
    assert parse_issue_reference("psf/requests") == ("psf", "requests", None)
    assert parse_issue_reference("https://github.com/pallets/click") == ("pallets", "click", None)

    with pytest.raises(ValueError, match="Invalid GitHub reference"):
        parse_issue_reference("not-a-valid-url-or-slug")


def test_extractions():
    sample_text = """
    ### Expected
    Expected function to return 42.

    ### Actual
    It raised TypeError:

    ```python
    import foo
    foo.bar(None)
    ```

    Traceback (most recent call last):
      File "foo/core.py", line 12, in bar
        return val + 1
    TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'

    Tested on Python 3.12.1 and v2.4.0. Look at `foo/utils.py`.
    """
    blocks = extract_code_blocks(sample_text)
    assert len(blocks) == 1
    assert "foo.bar(None)" in blocks[0]

    tracebacks = extract_tracebacks(sample_text)
    assert len(tracebacks) == 1
    assert "TypeError: unsupported operand" in tracebacks[0]

    files = extract_mentioned_files(sample_text)
    assert "foo/core.py" in files or "foo/utils.py" in files

    symbols = extract_mentioned_symbols(sample_text)
    assert "bar" in symbols or "foo/utils.py" in symbols

    versions = extract_version_strings(sample_text)
    assert any("3.12" in v for v in versions)

    exp_vs_act = extract_expected_vs_actual(sample_text)
    assert "Expected" in exp_vs_act
    assert "Actual" in exp_vs_act


def test_fetch_issue_pasted_only():
    client = GitHubClient()
    issue = client.fetch_issue("pallets/click", pasted_text="Description of bug with traceback")
    assert issue.owner == "pallets"
    assert issue.repo == "click"
    assert issue.source == "pasted"
    assert "Description of bug" in issue.body


def test_fetch_issue_missing_number():
    client = GitHubClient()
    with pytest.raises(ValueError, match="No issue number provided"):
        client.fetch_issue("pallets/click")


def test_fetch_issue_404_mocked(monkeypatch):
    client = GitHubClient()

    def mock_get(*args, **kwargs):
        req = httpx.Request("GET", "https://api.github.com/repos/pallets/click/issues/99999")
        return httpx.Response(404, request=req)

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(ValueError, match="not found \\(404\\)"):
        client.fetch_issue("pallets/click#99999")


def test_fetch_issue_pull_request_rejected(monkeypatch):
    client = GitHubClient()

    def mock_get(*args, **kwargs):
        req = httpx.Request("GET", "https://api.github.com/repos/pallets/click/issues/100")
        return httpx.Response(
            200,
            json={"title": "PR", "body": "Fix bug", "pull_request": {"url": "..."}},
            request=req,
        )

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(ValueError, match="is a Pull Request, not an Issue"):
        client.fetch_issue("pallets/click#100")


def test_fetch_issue_rate_limit_exceeded(monkeypatch):
    client = GitHubClient()

    def mock_get(*args, **kwargs):
        req = httpx.Request("GET", "https://api.github.com/repos/pallets/click/issues/100")
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1800000000"}
        return httpx.Response(403, headers=headers, request=req)

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(RuntimeError, match="GitHub API rate limit exceeded"):
        client.fetch_issue("pallets/click#100")


def test_fetch_issue_success(monkeypatch):
    client = GitHubClient()

    def mock_get(self, url, *args, **kwargs):
        req = httpx.Request("GET", url)
        if "/comments" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "user": {"login": "maintainer"},
                        "author_association": "MEMBER",
                        "body": "Here is a test: ```assert False```",
                    }
                ],
                request=req,
            )
        return httpx.Response(
            200,
            json={
                "html_url": "https://github.com/pallets/click/issues/100",
                "title": "Cli runner bug",
                "body": "Cli runner fails on None input.",
                "labels": [{"name": "bug"}],
                "created_at": "2024-01-01T00:00:00Z",
                "state": "closed",
                "comments": 1,
                "comments_url": "https://api.github.com/repos/pallets/click/issues/100/comments",
            },
            request=req,
        )

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    issue = client.fetch_issue("pallets/click#100")
    assert issue.title == "Cli runner bug"
    assert issue.number == 100
    assert len(issue.comments) == 1
    assert "assert False" in issue.comments[0]["body"]
