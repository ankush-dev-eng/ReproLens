"""Security test asserting that benchmark ground-truth cannot leak to LLM prompts or retrieval."""

from reprolens.config import Config
from reprolens.indexer import RepoIndexer
from reprolens.llm.prompts import (
    ISSUE_UNDERSTANDING_PROMPT,
    REPRO_TEST_GENERATION_PROMPT,
    ROOT_CAUSE_PROMPT,
    SYSTEM_SECURITY_PROMPT,
)


def test_retrieval_cannot_reach_benchmark_private():
    """Verify that RepoIndexer and retrieval ignore benchmark_private directory."""
    project_root = Config.PROJECT_ROOT

    # Even if indexing from project root, benchmark_private must never be indexed
    indexer = RepoIndexer(project_root)
    # Exclude benchmark_private explicitly if scanned
    modules = indexer.build_index()

    for path in modules:
        assert "benchmark_private" not in path, f"Ground truth leak: {path} indexed!"


def test_prompts_contain_no_solution_references():
    """Assert that standard prompt templates do not contain any hardcoded fix commits or solutions."""
    prompts = [
        SYSTEM_SECURITY_PROMPT,
        ISSUE_UNDERSTANDING_PROMPT,
        ROOT_CAUSE_PROMPT,
        REPRO_TEST_GENERATION_PROMPT,
    ]
    forbidden_terms = [
        "benchmark_private",
        "ground_truth",
        "fix_commit",
        "hidden_test",
    ]
    for prompt in prompts:
        for term in forbidden_terms:
            assert term not in prompt, f"Prompt contains forbidden ground truth term: {term}"


def test_indexer_ignores_benchmark_private_relative(tmp_path):
    """Ensure RepoIndexer ignores benchmark_private directory when present in repo checkout."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "app.py").write_text("def run(): pass")

    private_dir = repo_dir / "benchmark_private"
    private_dir.mkdir()
    (private_dir / "solution.py").write_text("def secret_fix(): pass")

    indexer = RepoIndexer(repo_dir)
    modules = indexer.build_index()

    assert "src/app.py" in modules
    assert "benchmark_private/solution.py" not in modules
    assert not any("benchmark_private" in m for m in modules)
