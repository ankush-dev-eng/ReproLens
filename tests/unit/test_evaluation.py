"""Tests for benchmark evaluation harness and metrics calculation."""

from reprolens.db import Database
from reprolens.evaluation import BenchmarkEvaluator, run_evaluation_cli
from reprolens.models import EvalRun


def test_evaluator_manifest_loading(tmp_path):
    manifest_file = tmp_path / "test_manifest.yaml"
    manifest_file.write_text(
        """
cases:
  - id: "test-case-1"
    repo_url: "https://github.com/foo/bar"
    issue_url: "https://github.com/foo/bar/issues/1"
    base_commit: "abcdef"
    expected_symptom_category: "AssertionError"
    expected_result: "reproducible"
""",
        encoding="utf-8",
    )

    evaluator = BenchmarkEvaluator(manifest_path=manifest_file)
    cases = evaluator.load_manifest()
    assert len(cases) == 1
    assert cases[0]["id"] == "test-case-1"


def test_run_evaluation_metrics(tmp_path, monkeypatch):
    """Test full evaluation pipeline and metric calculation."""
    db_file = tmp_path / "eval_test.db"
    monkeypatch.setenv("REPROLENS_DB_PATH", str(db_file))
    db = Database(db_file)

    evaluator = BenchmarkEvaluator(db=db)
    eval_run = evaluator.run_evaluation()

    assert isinstance(eval_run, EvalRun)
    assert eval_run.total_cases >= 8
    assert eval_run.reproduction_rate >= 0.75
    assert eval_run.fail_to_pass_rate >= 0.80
    assert eval_run.false_reproduction_rate == 0.0

    # Verify stored in DB
    stored_runs = db.list_eval_runs()
    assert len(stored_runs) >= 1
    assert stored_runs[0].id == eval_run.id


def test_run_evaluation_cli():
    """Verify CLI execution helper returns 0."""
    exit_code = run_evaluation_cli()
    assert exit_code == 0
