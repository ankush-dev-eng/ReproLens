"""Tests for repository management, AST indexing, retrieval, and ref verification."""

import subprocess

from reprolens.indexer import RepoIndexer, parse_module_ast
from reprolens.models import GitHubIssue, SourceRef
from reprolens.refs import verify_source_ref
from reprolens.repo import RepositoryManager, slugify_repo_url
from reprolens.retrieval import extract_traceback_frames, retrieve_relevant_code


def test_slugify_repo_url():
    assert slugify_repo_url("https://github.com/pallets/click.git") == "pallets_click"
    assert slugify_repo_url("psf/requests") == "psf_requests"


def test_ast_parse_module_with_classes_and_functions():
    code = '''"""Sample module docstring."""

import os
from sys import argv

class MyClass:
    """Class docstring."""
    def method_one(self, a: int, b: str = "default") -> bool:
        return True

def standalone_func(x, *args, **kwargs):
    """Function docstring."""
    return x * 2
'''
    mod = parse_module_ast("sample.py", code)
    assert mod.docstring == "Sample module docstring."
    assert len(mod.classes) == 1
    assert mod.classes[0].name == "MyClass"
    assert len(mod.classes[0].methods) == 1
    assert mod.classes[0].methods[0].name == "method_one"
    assert "(self, a, b)" in mod.classes[0].methods[0].signature

    assert len(mod.functions) == 1
    assert mod.functions[0].name == "standalone_func"
    assert "(x, *args, **kwargs)" in mod.functions[0].signature
    assert "os" in mod.imports
    assert "sys.argv" in mod.imports


def test_ast_parse_syntax_error_tolerated():
    bad_code = "def broken_func(:\n    pass"
    mod = parse_module_ast("bad.py", bad_code)
    assert mod.syntax_error is not None
    assert "SyntaxError" in mod.syntax_error


def test_indexer_find_symbol(tmp_path):
    repo_dir = tmp_path / "mini_repo"
    repo_dir.mkdir()
    (repo_dir / "calc.py").write_text(
        "class Calculator:\n    def add(self, a, b):\n        return a + b\n"
    )

    indexer = RepoIndexer(repo_dir)
    modules = indexer.build_index()
    assert "calc.py" in modules

    matches = indexer.find_symbol("Calculator.add")
    assert len(matches) == 1
    assert matches[0][1].name == "add"


def test_retrieval_traceback_priority(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    (repo_dir / "engine.py").write_text(
        "# Header\n" * 10
        + "def faulty_routine():\n    raise ValueError('broken value')\n"
        + "# Footer\n" * 10
    )

    indexer = RepoIndexer(repo_dir)
    indexer.build_index()

    tb = """Traceback (most recent call last):
  File "engine.py", line 11, in faulty_routine
    raise ValueError('broken value')
ValueError: broken value"""

    issue = GitHubIssue(
        owner="test",
        repo="repo",
        number=1,
        url="https://github.com/test/repo/issues/1",
        title="Bug in routine",
        body="Details",
        tracebacks=[tb],
    )

    excerpts = retrieve_relevant_code(repo_dir, indexer, issue)
    assert len(excerpts) >= 1
    assert excerpts[0].path == "engine.py"
    assert excerpts[0].score == 100.0


def test_extract_traceback_frames():
    tb = 'File "/var/app/pkg/foo.py", line 42, in run\nFile "bar.py", line 10, in step'
    frames = extract_traceback_frames(tb)
    assert len(frames) == 2
    assert frames[0] == ("/var/app/pkg/foo.py", 42)
    assert frames[1] == ("bar.py", 10)


def test_verify_source_ref(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "src" / "sample.py"
    file_path.parent.mkdir()
    file_path.write_text("def hello():\n    return 'world'\n")

    # Valid reference with exact snippet
    ref_valid = SourceRef(
        path="src/sample.py",
        start_line=1,
        end_line=2,
        snippet="def hello():\n    return 'world'",
    )
    res = verify_source_ref(repo_dir, ref_valid)
    assert res.verified is True

    # Invalid line bounds
    ref_bad_line = SourceRef(path="src/sample.py", start_line=1, end_line=100)
    assert verify_source_ref(repo_dir, ref_bad_line).verified is False

    # Snippet mismatch
    ref_mismatch = SourceRef(
        path="src/sample.py",
        start_line=1,
        end_line=2,
        snippet="def different(): pass",
    )
    assert verify_source_ref(repo_dir, ref_mismatch).verified is False

    # Non-existent file
    ref_absent = SourceRef(path="src/missing.py", start_line=1, end_line=1)
    assert verify_source_ref(repo_dir, ref_absent).verified is False

    # Path traversal attempt
    ref_traversal = SourceRef(path="../outside.py", start_line=1, end_line=1)
    assert verify_source_ref(repo_dir, ref_traversal).verified is False


def test_repo_worktree_lifecycle(tmp_path):
    repo_dir = tmp_path / "git_fixture"
    repo_dir.mkdir()

    # Initialize a test git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    (repo_dir / "file.txt").write_text("initial commit")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    mgr = RepositoryManager(cache_base_dir=tmp_path / "cache")
    sha = mgr.resolve_revision(repo_dir)
    assert len(sha) == 40

    wt = mgr.checkout_worktree(repo_dir, sha)
    assert wt.exists()
    assert (wt / "file.txt").read_text() == "initial commit"

    mgr.cleanup_worktree(repo_dir, wt)
    assert not wt.exists()
