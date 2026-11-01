"""SQLite Database and Evidence Ledger Persistence for ReproLens."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reprolens.config import Config
from reprolens.models import (
    Attempt,
    BisectRun,
    Claim,
    ClaimKind,
    ClaimStatus,
    EvalRun,
    ExecutionMode,
    ExecutionOrigin,
    Investigation,
    InvestigationStatus,
    LLMCall,
    PatchRecord,
    SourceRef,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    issue_number INTEGER,
    issue_url TEXT NOT NULL,
    commit_sha TEXT DEFAULT '',
    issue_summary TEXT DEFAULT '',
    final_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    duration_sec REAL DEFAULT 0.0,
    mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium',
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id)
);

CREATE TABLE IF NOT EXISTS source_refs (
    id TEXT PRIMARY KEY,
    claim_id TEXT,
    investigation_id TEXT NOT NULL,
    path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    snippet TEXT DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    test_source TEXT NOT NULL,
    status TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    stdout TEXT DEFAULT '',
    stderr TEXT DEFAULT '',
    duration_sec REAL DEFAULT 0.0,
    execution_origin TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id)
);

CREATE TABLE IF NOT EXISTS patches (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    diff TEXT NOT NULL,
    status TEXT NOT NULL,
    baseline_passed INTEGER DEFAULT 0,
    patched_passed INTEGER DEFAULT 0,
    regression_clean INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id)
);

CREATE TABLE IF NOT EXISTS bisect_runs (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    status TEXT NOT NULL,
    run_count INTEGER DEFAULT 3,
    pass_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id)
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id TEXT PRIMARY KEY,
    investigation_id TEXT,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL,
    latency_sec REAL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    run_date TEXT NOT NULL,
    model_id TEXT NOT NULL,
    total_cases INTEGER DEFAULT 0,
    reproduced_count INTEGER DEFAULT 0,
    fail_to_pass_count INTEGER DEFAULT 0,
    false_reproduction_count INTEGER DEFAULT 0,
    invalid_test_count INTEGER DEFAULT 0,
    env_error_count INTEGER DEFAULT 0,
    reproduction_rate REAL DEFAULT 0.0,
    fail_to_pass_rate REAL DEFAULT 0.0,
    false_reproduction_rate REAL DEFAULT 0.0,
    invalid_test_rate REAL DEFAULT 0.0,
    env_error_rate REAL DEFAULT 0.0,
    total_duration_sec REAL DEFAULT 0.0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL
);

CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_inv ON claims(investigation_id);
CREATE INDEX IF NOT EXISTS idx_attempts_inv ON attempts(investigation_id);
CREATE INDEX IF NOT EXISTS idx_source_refs_inv ON source_refs(investigation_id);
"""


class Database:
    """ReproLens SQLite storage manager."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or Config.get_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ---------------- Investigation Operations ---------------- #

    def save_investigation(self, inv: Investigation) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO investigations (id, repo, issue_number, issue_url, commit_sha, issue_summary, final_status, created_at, duration_sec, mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repo=excluded.repo,
                    issue_number=excluded.issue_number,
                    issue_url=excluded.issue_url,
                    commit_sha=excluded.commit_sha,
                    issue_summary=excluded.issue_summary,
                    final_status=excluded.final_status,
                    duration_sec=excluded.duration_sec,
                    mode=excluded.mode
                """,
                (
                    inv.id,
                    inv.repo,
                    inv.issue_number,
                    inv.issue_url,
                    inv.commit_sha,
                    inv.issue_summary,
                    inv.final_status.value,
                    inv.created_at.isoformat(),
                    inv.duration_sec,
                    inv.mode.value,
                ),
            )

    def get_investigation(self, inv_id: str) -> Investigation | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)).fetchone()
            if not row:
                return None
            return Investigation(
                id=row["id"],
                repo=row["repo"],
                issue_number=row["issue_number"],
                issue_url=row["issue_url"],
                commit_sha=row["commit_sha"],
                issue_summary=row["issue_summary"],
                final_status=InvestigationStatus(row["final_status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                duration_sec=row["duration_sec"],
                mode=ExecutionMode(row["mode"]),
            )

    def list_investigations(self, limit: int = 50) -> list[Investigation]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investigations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                Investigation(
                    id=r["id"],
                    repo=r["repo"],
                    issue_number=r["issue_number"],
                    issue_url=r["issue_url"],
                    commit_sha=r["commit_sha"],
                    issue_summary=r["issue_summary"],
                    final_status=InvestigationStatus(r["final_status"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    duration_sec=r["duration_sec"],
                    mode=ExecutionMode(r["mode"]),
                )
                for r in rows
            ]

    # ---------------- Claims & Evidence Operations ---------------- #

    def save_claim(self, claim: Claim) -> None:
        import uuid

        claim_id = claim.id or str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO claims (id, investigation_id, kind, text, status, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    confidence=excluded.confidence
                """,
                (
                    claim_id,
                    claim.investigation_id,
                    claim.kind.value,
                    claim.text,
                    claim.status.value,
                    claim.confidence,
                    claim.created_at.isoformat(),
                ),
            )
            if claim.source_ref:
                ref = claim.source_ref
                ref_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO source_refs (id, claim_id, investigation_id, path, start_line, end_line, snippet, verified, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ref_id,
                        claim_id,
                        claim.investigation_id,
                        ref.path,
                        ref.start_line,
                        ref.end_line,
                        ref.snippet,
                        1 if ref.verified else 0,
                        datetime.now(UTC).isoformat(),
                    ),
                )

    def list_claims(self, investigation_id: str) -> list[Claim]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE investigation_id = ? ORDER BY created_at ASC",
                (investigation_id,),
            ).fetchall()
            claims = []
            for r in rows:
                ref_row = conn.execute(
                    "SELECT * FROM source_refs WHERE claim_id = ?", (r["id"],)
                ).fetchone()
                source_ref = None
                if ref_row:
                    source_ref = SourceRef(
                        path=ref_row["path"],
                        start_line=ref_row["start_line"],
                        end_line=ref_row["end_line"],
                        snippet=ref_row["snippet"],
                        verified=bool(ref_row["verified"]),
                    )
                claims.append(
                    Claim(
                        id=r["id"],
                        investigation_id=r["investigation_id"],
                        kind=ClaimKind(r["kind"]),
                        text=r["text"],
                        status=ClaimStatus(r["status"]),
                        confidence=r["confidence"],
                        source_ref=source_ref,
                        created_at=datetime.fromisoformat(r["created_at"]),
                    )
                )
            return claims

    # ---------------- Attempts Operations ---------------- #

    def save_attempt(self, attempt: Attempt) -> None:
        import uuid

        att_id = attempt.id or str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO attempts (id, investigation_id, attempt_no, test_source, status, exit_code, stdout, stderr, duration_sec, execution_origin, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    att_id,
                    attempt.investigation_id,
                    attempt.attempt_no,
                    attempt.test_source,
                    attempt.status.value,
                    attempt.exit_code,
                    attempt.stdout,
                    attempt.stderr,
                    attempt.duration_sec,
                    attempt.execution_origin.value,
                    attempt.created_at.isoformat(),
                ),
            )

    def list_attempts(self, investigation_id: str) -> list[Attempt]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM attempts WHERE investigation_id = ? ORDER BY attempt_no ASC",
                (investigation_id,),
            ).fetchall()
            return [
                Attempt(
                    id=r["id"],
                    investigation_id=r["investigation_id"],
                    attempt_no=r["attempt_no"],
                    test_source=r["test_source"],
                    status=InvestigationStatus(r["status"]),
                    exit_code=r["exit_code"],
                    stdout=r["stdout"],
                    stderr=r["stderr"],
                    duration_sec=r["duration_sec"],
                    execution_origin=ExecutionOrigin(r["execution_origin"]),
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]

    # ---------------- Patches Operations ---------------- #

    def save_patch(self, patch: PatchRecord) -> None:
        import uuid

        patch_id = patch.id or str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO patches (id, investigation_id, diff, status, baseline_passed, patched_passed, regression_clean, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patch_id,
                    patch.investigation_id,
                    patch.diff,
                    patch.status.value,
                    1 if patch.baseline_passed else 0,
                    1 if patch.patched_passed else 0,
                    1 if patch.regression_clean else 0,
                    patch.created_at.isoformat(),
                ),
            )

    # ---------------- Bisect Operations ---------------- #

    def save_bisect_run(self, bisect: BisectRun) -> None:
        import uuid

        b_id = bisect.id or str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO bisect_runs (id, investigation_id, commit_sha, status, run_count, pass_count, fail_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    b_id,
                    bisect.investigation_id,
                    bisect.commit_sha,
                    bisect.status,
                    bisect.run_count,
                    bisect.pass_count,
                    bisect.fail_count,
                    bisect.created_at.isoformat(),
                ),
            )

    def list_bisect_runs(self, investigation_id: str) -> list[BisectRun]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bisect_runs WHERE investigation_id = ? ORDER BY created_at ASC",
                (investigation_id,),
            ).fetchall()
            return [
                BisectRun(
                    id=r["id"],
                    investigation_id=r["investigation_id"],
                    commit_sha=r["commit_sha"],
                    status=r["status"],
                    run_count=r["run_count"],
                    pass_count=r["pass_count"],
                    fail_count=r["fail_count"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]

    # ---------------- LLM Calls & Cache ---------------- #

    def save_llm_call(self, call: LLMCall) -> None:
        import uuid

        call_id = call.id or str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_calls (id, investigation_id, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_sec, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    call.investigation_id,
                    call.model,
                    call.prompt_tokens,
                    call.completion_tokens,
                    call.total_tokens,
                    call.cost_usd,
                    call.latency_sec,
                    call.created_at.isoformat(),
                ),
            )

    def get_cached_llm(self, cache_key: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM llm_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            if row:
                try:
                    return json.loads(row["response_json"])
                except Exception:
                    return None
            return None

    def set_cached_llm(self, cache_key: str, response_dict: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (cache_key, response_json, created_at)
                VALUES (?, ?, ?)
                """,
                (cache_key, json.dumps(response_dict), datetime.now(UTC).isoformat()),
            )

    # ---------------- Evaluation Runs ---------------- #

    def save_eval_run(self, eval_run: EvalRun) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO eval_runs (
                    id, run_date, model_id, total_cases, reproduced_count, fail_to_pass_count,
                    false_reproduction_count, invalid_test_count, env_error_count, reproduction_rate,
                    fail_to_pass_rate, false_reproduction_rate, invalid_test_rate, env_error_rate,
                    total_duration_sec, total_tokens, total_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_run.id,
                    eval_run.run_date.isoformat(),
                    eval_run.model_id,
                    eval_run.total_cases,
                    eval_run.reproduced_count,
                    eval_run.fail_to_pass_count,
                    eval_run.false_reproduction_count,
                    eval_run.invalid_test_count,
                    eval_run.env_error_count,
                    eval_run.reproduction_rate,
                    eval_run.fail_to_pass_rate,
                    eval_run.false_reproduction_rate,
                    eval_run.invalid_test_rate,
                    eval_run.env_error_rate,
                    eval_run.total_duration_sec,
                    eval_run.total_tokens,
                    eval_run.total_cost_usd,
                ),
            )

    def list_eval_runs(self) -> list[EvalRun]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM eval_runs ORDER BY run_date DESC").fetchall()
            return [
                EvalRun(
                    id=r["id"],
                    run_date=datetime.fromisoformat(r["run_date"]),
                    model_id=r["model_id"],
                    total_cases=r["total_cases"],
                    reproduced_count=r["reproduced_count"],
                    fail_to_pass_count=r["fail_to_pass_count"],
                    false_reproduction_count=r["false_reproduction_count"],
                    invalid_test_count=r["invalid_test_count"],
                    env_error_count=r["env_error_count"],
                    reproduction_rate=r["reproduction_rate"],
                    fail_to_pass_rate=r["fail_to_pass_rate"],
                    false_reproduction_rate=r["false_reproduction_rate"],
                    invalid_test_rate=r["invalid_test_rate"],
                    env_error_rate=r["env_error_rate"],
                    total_duration_sec=r["total_duration_sec"],
                    total_tokens=r["total_tokens"],
                    total_cost_usd=r["total_cost_usd"],
                )
                for r in rows
            ]
