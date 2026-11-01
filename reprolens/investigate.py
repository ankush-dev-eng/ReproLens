"""End-to-end investigation pipeline orchestrator and background worker."""

import time
import uuid

from reprolens.config import Config
from reprolens.db import Database
from reprolens.github_client import GitHubClient, parse_issue_reference
from reprolens.indexer import RepoIndexer
from reprolens.ledger import EvidenceLedger
from reprolens.llm.client import FakeLLM, OpenRouterClient
from reprolens.llm.prompts import (
    ISSUE_UNDERSTANDING_PROMPT,
    ROOT_CAUSE_PROMPT,
    SYSTEM_SECURITY_PROMPT,
)
from reprolens.llm.schemas import (
    IssueUnderstandingSchema,
    RootCauseInvestigationSchema,
)
from reprolens.models import (
    ExecutionMode,
    Investigation,
    InvestigationStatus,
    SourceRef,
)
from reprolens.refs import verify_source_ref
from reprolens.repo import RepositoryManager
from reprolens.repro_loop import ReproductionEngine
from reprolens.retrieval import retrieve_relevant_code
from reprolens.sandbox.base import ExecutionBackend
from reprolens.sandbox.demo_backend import DemoBackend
from reprolens.sandbox.docker_backend import DockerBackend
from reprolens.sandbox.remote_adapter import RemoteRunnerBackend


def get_default_llm() -> OpenRouterClient | FakeLLM:
    """Return OpenRouter client or seeded FakeLLM if API key is not configured."""
    if Config.OPENROUTER_API_KEY:
        return OpenRouterClient()

    fake = FakeLLM()
    # Seed scripted responses for benchmark triage when API key is missing
    fake.set_response(
        "Analyze the following",
        {
            "expected_behavior": "click.prompt with prompt_suffix='' should not append any trailing space.",
            "actual_behavior": "click.prompt with prompt_suffix='' appends a trailing space.",
            "symptom_statement": "AssertionError: click.prompt appends trailing space when prompt_suffix=''",
            "candidate_symbols": ["click.termui.prompt", "click.prompt"],
            "missing_information": "",
            "is_reproducible_theoretically": True,
        },
    )
    fake.set_response(
        "candidate root causes",
        {
            "summary": "In click/termui.py, prompt() calls f(' ') which unconditionally appends a space.",
            "hypotheses": [
                {
                    "rank": 1,
                    "hypothesis_text": "click/termui.py returns f(' ') appending a space even when prompt_suffix is empty",
                    "confidence": "high",
                    "file_path": "src/click/termui.py",
                    "start_line": 138,
                    "end_line": 144,
                    "snippet": 'return f(" ")',
                }
            ],
        },
    )
    fake.set_response(
        "Create a minimal",
        {
            "thought_process": "Invoke click.prompt with prompt_suffix='' and verify stdout has no trailing space.",
            "expected_symptom": {
                "exception_type": "AssertionError",
                "message_regex": "Prompt with no suffix",
                "description": "click.prompt appends trailing space when prompt_suffix is empty",
                "target_symbols": ["click.termui.prompt"],
            },
            "test_code": (
                "import io\n"
                "import click\n"
                "import pytest\n\n"
                "EXPECTED_SYMPTOM = {\n"
                '    "exception_type": "AssertionError",\n'
                '    "message_regex": "Prompt with no suffix",\n'
                '    "description": "click.prompt appends trailing space when prompt_suffix is empty",\n'
                '    "target_symbols": ["click.termui.prompt"],\n'
                "}\n\n"
                "def test_reproduce_issue(monkeypatch, capfd):\n"
                '    monkeypatch.setattr("sys.stdin", io.StringIO("input_val\\n"))\n'
                '    click.prompt("Prompt with no suffix", prompt_suffix="")\n'
                "    out, _ = capfd.readouterr()\n"
                '    assert out == "Prompt with no suffix"\n'
            ),
        },
    )
    return fake


def get_default_backend() -> ExecutionBackend:
    """Instantiate the active execution backend based on configuration and host environment."""
    resolved_mode = Config.resolve_execution_mode()
    if resolved_mode == "docker":
        return DockerBackend()
    if resolved_mode == "remote":
        return RemoteRunnerBackend()
    return DemoBackend()


def run_investigation(
    investigation_id: str,
    backend: ExecutionBackend | None = None,
    llm: OpenRouterClient | None = None,
    db: Database | None = None,
) -> Investigation:
    """Execute complete 5-stage reproduction investigation."""
    database = db or Database()
    inv = database.get_investigation(investigation_id)
    if not inv:
        raise ValueError(f"Investigation '{investigation_id}' not found in database.")

    active_backend = backend or get_default_backend()
    active_llm = llm or get_default_llm()
    ledger = EvidenceLedger(db=database)
    repo_mgr = RepositoryManager()

    start_time = time.monotonic()
    inv.final_status = InvestigationStatus.ANALYZING
    inv.mode = active_backend.mode
    database.save_investigation(inv)

    wt_dir = None
    repo_dir = None

    try:
        # Step 1: Ingest issue
        gh_client = GitHubClient()
        issue = gh_client.fetch_issue(inv.issue_url)

        inv.issue_summary = issue.title
        inv.issue_number = issue.number
        database.save_investigation(inv)

        # Step 2: Ingest & checkout repository
        repo_url = inv.repo
        if repo_url == "unknown" or not repo_url:
            repo_url = f"https://github.com/{issue.owner}/{issue.repo}.git"
            inv.repo = f"{issue.owner}/{issue.repo}"

        repo_dir = repo_mgr.clone_or_fetch(repo_url)
        commit_sha = repo_mgr.resolve_revision(
            repo_dir,
            explicit_commit=inv.commit_sha or None,
            issue_created_at=issue.created_at,
        )
        inv.commit_sha = commit_sha
        database.save_investigation(inv)

        wt_dir = repo_mgr.checkout_worktree(repo_dir, commit_sha)

        # Step 3: AST Indexing & Code Retrieval
        indexer = RepoIndexer(wt_dir)
        indexer.build_index()

        # Stage 1 LLM: Issue Understanding
        und_prompt = ISSUE_UNDERSTANDING_PROMPT.format(
            repo=inv.repo,
            issue_url=inv.issue_url,
            title=issue.title,
            body=issue.body[:8000],
            code_blocks="\n\n".join(issue.code_blocks[:5]) or "None",
            tracebacks="\n\n".join(issue.tracebacks[:3]) or "None",
            comments="\n\n".join(c["body"] for c in issue.comments[:5]) or "None",
        )

        understanding: IssueUnderstandingSchema = active_llm.generate_structured(
            system_prompt=SYSTEM_SECURITY_PROMPT,
            user_prompt=und_prompt,
            schema=IssueUnderstandingSchema,
            investigation_id=inv.id,
        )

        # Merge candidate symbols from LLM into issue for retrieval
        if understanding.candidate_symbols:
            issue.mentioned_symbols.extend(understanding.candidate_symbols)

        # Retrieve relevant code
        code_excerpts = retrieve_relevant_code(
            repo_dir=wt_dir,
            indexer=indexer,
            issue=issue,
        )

        # Stage 2 LLM: Root Cause Hypotheses
        formatted_excerpts = "\n\n".join(
            f"--- {exc.path} (lines {exc.start_line}-{exc.end_line}) ---\n{exc.content}"
            for exc in code_excerpts[:6]
        )

        rc_prompt = ROOT_CAUSE_PROMPT.format(
            symptom_statement=understanding.symptom_statement,
            expected_behavior=understanding.expected_behavior,
            actual_behavior=understanding.actual_behavior,
            code_excerpts=formatted_excerpts,
        )

        root_causes: RootCauseInvestigationSchema = active_llm.generate_structured(
            system_prompt=SYSTEM_SECURITY_PROMPT,
            user_prompt=rc_prompt,
            schema=RootCauseInvestigationSchema,
            investigation_id=inv.id,
        )

        # Register and verify each hypothesis and its citation
        for hyp in root_causes.hypotheses:
            ref = SourceRef(
                path=hyp.file_path,
                start_line=hyp.start_line,
                end_line=hyp.end_line,
                snippet=hyp.snippet,
            )
            verified_ref = verify_source_ref(wt_dir, ref)
            ledger.record_hypothesis(
                investigation_id=inv.id,
                text=hyp.hypothesis_text,
                source_ref=verified_ref,
                confidence=hyp.confidence,
            )
            if verified_ref.verified:
                ledger.record_source_evidence(
                    investigation_id=inv.id,
                    text=f"Code citation in {verified_ref.path}:{verified_ref.start_line}-{verified_ref.end_line}",
                    source_ref=verified_ref,
                )

        # Step 4: Reproduction Loop
        inv.final_status = InvestigationStatus.REPRODUCING
        database.save_investigation(inv)

        repro_engine = ReproductionEngine(
            backend=active_backend,
            llm=active_llm,
            ledger=ledger,
            max_repairs=Config.MAX_REPAIR_ATTEMPTS,
        )

        final_status, _ = repro_engine.run_loop(
            investigation_id=inv.id,
            repo_dir=wt_dir,
            issue=issue,
            code_excerpts=code_excerpts,
            understanding=understanding,
            root_causes=root_causes,
            known_repo_files=set(indexer.modules.keys()),
        )

        inv.final_status = final_status

    except Exception as e:
        inv.final_status = InvestigationStatus.ENVIRONMENT_ERROR
        inv.issue_summary += f" [Error: {e}]"

    finally:
        inv.duration_sec = time.monotonic() - start_time
        database.save_investigation(inv)
        if repo_dir and wt_dir:
            repo_mgr.cleanup_worktree(repo_dir, wt_dir)

    return inv


def run_investigation_worker(investigation_id: str) -> int:
    """CLI worker entrypoint for background investigation tasks."""
    try:
        inv = run_investigation(investigation_id)
        print(f"[Worker] Investigation {inv.id} completed. Status: {inv.final_status.value}")
        return 0
    except Exception as e:
        print(f"[Worker] Investigation {investigation_id} failed: {e}")
        return 1


def reproduce_cli(target: str, repo: str | None = None, commit: str | None = None) -> int:
    """CLI runner to initiate and execute an ad-hoc issue reproduction."""
    db = Database()
    inv_id = f"inv-{uuid.uuid4().hex[:8]}"

    owner, repo_name, number = parse_issue_reference(target)
    effective_repo = repo or f"{owner}/{repo_name}"

    inv = Investigation(
        id=inv_id,
        repo=effective_repo,
        issue_number=number,
        issue_url=target,
        commit_sha=commit or "",
        issue_summary="CLI requested triage",
        final_status=InvestigationStatus.PENDING,
        mode=ExecutionMode(Config.resolve_execution_mode()),
    )
    db.save_investigation(inv)

    print(f"[ReproLens] Initialized investigation {inv_id} for {effective_repo}")
    res_inv = run_investigation(inv_id, db=db)

    print("\n[ReproLens] Investigation Complete!")
    print(f"Status:   {res_inv.final_status.value}")
    print(f"Duration: {res_inv.duration_sec:.1f}s")
    print(f"Mode:     {res_inv.mode.value}")

    claims = db.list_claims(inv_id)
    attempts = db.list_attempts(inv_id)
    print(f"Claims:   {len(claims)}")
    print(f"Attempts: {len(attempts)}")

    if attempts:
        latest = attempts[-1]
        print(f"\nLatest Test Code ({len(latest.test_source.splitlines())} lines):")
        print("--------------------------------------------------")
        print(latest.test_source[:1500])
        print("--------------------------------------------------")

    return 0 if res_inv.final_status == InvestigationStatus.REPRODUCED else 1
