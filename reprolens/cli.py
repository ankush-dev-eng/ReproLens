"""CLI entrypoint for ReproLens workflows."""

import argparse
import sys

from reprolens import __version__
from reprolens.config import Config


def cmd_bisect(args: argparse.Namespace) -> int:
    """Run automated git bisect for an investigation."""
    inv_id = args.investigation_id
    from reprolens.bisect import GitBisectEngine
    from reprolens.db import Database
    from reprolens.repo import RepositoryManager

    db = Database()
    inv = db.get_investigation(inv_id)
    if not inv:
        print(f"Investigation {inv_id} not found.")
        return 1

    attempts = db.list_attempts(inv_id)
    if not attempts:
        print(f"No reproducer test available for {inv_id}.")
        return 1

    repo_mgr = RepositoryManager()
    repo_dir = repo_mgr.get_repo_cache_dir(inv.repo)
    if not repo_dir.exists():
        repo_dir = repo_mgr.clone_or_fetch(inv.repo)

    test_source = attempts[-1].test_source
    print(f"[ReproLens] Launching automated git bisect for {inv_id} on {inv.repo}...")
    engine = GitBisectEngine(repo_dir=repo_dir, db=db)
    result = engine.bisect(
        investigation_id=inv.id,
        buggy_commit=inv.commit_sha or "HEAD",
        test_source=test_source,
    )

    print("\n[Bisect Complete!]")
    print(f"Culprit Commit:  {result.culprit_commit}")
    print(f"Commit Message:  {result.culprit_message}")
    print(f"Author:          {result.culprit_author}")
    print(f"Steps Tested:    {result.steps_count} revisions in {result.duration_sec:.2f}s")
    return 0 if result.success else 1


def cmd_investigate(args: argparse.Namespace) -> int:
    """Run an investigation in background worker process."""
    inv_id = args.investigation_id
    print(f"[ReproLens] Running investigation worker for ID: {inv_id}")
    # Will be invoked by investigate.py worker
    from reprolens.investigate import run_investigation_worker

    return run_investigation_worker(inv_id)


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Ad-hoc issue reproduction from CLI."""
    print(f"[ReproLens] Reproducing issue: {args.target}")
    from reprolens.investigate import reproduce_cli

    return reproduce_cli(args.target, repo=args.repo, commit=args.commit)


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Run benchmark evaluation suite."""
    print("[ReproLens] Running benchmark evaluation...")
    from reprolens.evaluation import run_evaluation_cli

    return run_evaluation_cli(manifest_path=args.manifest)


def cmd_sandbox_clean(args: argparse.Namespace) -> int:
    """Clean up dangling ReproLens Docker containers and temp volumes."""
    print("[ReproLens] Cleaning up sandbox containers...")
    from reprolens.sandbox.docker_backend import clean_sandbox_containers

    return clean_sandbox_containers()


def cmd_status(args: argparse.Namespace) -> int:
    """Inspect system configuration and investigation status."""
    from reprolens.db import Database

    db = Database()
    mode = Config.resolve_execution_mode()
    print(f"ReproLens Engine v{__version__}")
    print(f"Execution Mode: {mode.upper()} (Docker available: {Config.is_docker_available()})")
    print(f"Database: {db.db_path}")

    if args.investigation_id:
        inv = db.get_investigation(args.investigation_id)
        if not inv:
            print(f"Investigation {args.investigation_id} not found.")
            return 1
        print(f"ID: {inv.id}")
        print(f"Repo: {inv.repo} (Issue: #{inv.issue_number})")
        print(f"Status: {inv.final_status.value}")
        print(f"Duration: {inv.duration_sec:.1f}s")
        claims = db.list_claims(inv.id)
        attempts = db.list_attempts(inv.id)
        print(f"Claims: {len(claims)} | Attempts: {len(attempts)}")
    else:
        invs = db.list_investigations(limit=10)
        print(f"\nRecent Investigations ({len(invs)}):")
        for inv in invs:
            print(f" - [{inv.final_status.value}] {inv.id}: {inv.repo}#{inv.issue_number}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reprolens",
        description="ReproLens: AI-Powered GitHub Issue Reproduction Engine",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # investigate
    inv_parser = subparsers.add_parser(
        "investigate", help="Run background worker for an investigation"
    )
    inv_parser.add_argument("investigation_id", help="Investigation ID to execute")
    inv_parser.set_defaults(func=cmd_investigate)

    # reproduce
    repro_parser = subparsers.add_parser("reproduce", help="Ad-hoc issue reproduction")
    repro_parser.add_argument("target", help="GitHub issue URL or path to issue file")
    repro_parser.add_argument("--repo", help="Target git repository URL", default=None)
    repro_parser.add_argument("--commit", help="Target commit SHA", default=None)
    repro_parser.set_defaults(func=cmd_reproduce)

    # bisect
    bisect_parser = subparsers.add_parser("bisect", help="Run automated git bisect")
    bisect_parser.add_argument("investigation_id", help="Investigation ID with reproduced test")
    bisect_parser.set_defaults(func=cmd_bisect)

    # evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Run benchmark evaluation")
    eval_parser.add_argument("--manifest", help="Path to manifest.yaml", default=None)
    eval_parser.set_defaults(func=cmd_evaluate)

    # sandbox-clean
    clean_parser = subparsers.add_parser(
        "sandbox-clean", help="Clean up sandbox containers and temp files"
    )
    clean_parser.set_defaults(func=cmd_sandbox_clean)

    # status
    status_parser = subparsers.add_parser("status", help="Show system and investigation status")
    status_parser.add_argument("investigation_id", nargs="?", help="Optional investigation ID")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
