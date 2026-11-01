"""New Investigation page for ReproLens."""

import subprocess
import sys
import uuid

import streamlit as st

from reprolens.config import Config
from reprolens.db import Database
from reprolens.github_client import parse_issue_reference
from reprolens.models import ExecutionMode, Investigation, InvestigationStatus
from ui.theme import render_header

render_header()

st.title("Start New Investigation")
st.markdown(
    "Provide a GitHub issue reference to initiate autonomous AST indexing, root cause analysis, "
    "and sandboxed test reproduction."
)

mode = Config.resolve_execution_mode()
if mode == "demo":
    st.info(
        "💡 **Demo Mode Active:** Because Docker daemon is not detected in host PATH, execution is safe and deterministic "
        "using recorded benchmark test environments. Select a curated benchmark sample below for instant reproduction."
    )

st.subheader("⚡ Quick Launch Benchmark Samples")
st.caption("Click a sample to pre-fill the form with verified historical issues:")

c_btn1, c_btn2, c_btn3 = st.columns(3)
with c_btn1:
    if st.button("📌 pallets/click #3019", use_container_width=True):
        st.session_state["field_repo"] = "pallets/click"
        st.session_state["field_issue"] = "https://github.com/pallets/click/issues/3019"
        st.session_state["field_commit"] = "c096a10e8b59e48f77c65372a9c17f8226c128c5"
        st.rerun()

with c_btn2:
    if st.button("📌 marshmallow-code/marshmallow #1842", use_container_width=True):
        st.session_state["field_repo"] = "marshmallow-code/marshmallow"
        st.session_state["field_issue"] = (
            "https://github.com/marshmallow-code/marshmallow/issues/1842"
        )
        st.session_state["field_commit"] = ""
        st.rerun()

with c_btn3:
    if st.button("📌 psf/requests #4175", use_container_width=True):
        st.session_state["field_repo"] = "psf/requests"
        st.session_state["field_issue"] = "https://github.com/psf/requests/issues/4175"
        st.session_state["field_commit"] = ""
        st.rerun()

st.markdown("---")

with st.form("new_investigation_form"):
    repo_input = st.text_input(
        "Target Repository (URL or owner/repo)",
        value=st.session_state.get("field_repo", ""),
        placeholder="e.g. pallets/click or https://github.com/pallets/click",
        help="GitHub repository containing the issue",
    )

    issue_input = st.text_input(
        "GitHub Issue (URL or #number)",
        value=st.session_state.get("field_issue", ""),
        placeholder="e.g. https://github.com/pallets/click/issues/3019 or #3019",
        help="Full GitHub issue URL or issue number within the target repository",
    )

    commit_sha = st.text_input(
        "Base Commit SHA (Optional)",
        value=st.session_state.get("field_commit", ""),
        placeholder="e.g. c096a10e8b59e48f77c65372a9c17f8226c128c5",
        help="Exact commit to check out. If left blank, ReproLens resolves the last commit before the issue was opened.",
    )

    model_choice = st.selectbox(
        "Reasoning LLM Engine",
        [
            f"OpenRouter Default ({Config.MODEL})",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "google/gemini-2.0-flash-001",
            "Scripted / Offline Benchmark Replay",
        ],
        index=0,
        help="Model used for Stage 1 (Issue Understanding), Stage 3 (Root Cause), and Stage 4 (Test Synthesis)",
    )

    pasted_issue = st.text_area(
        "Or Paste Raw Issue Details (Optional fallback)",
        placeholder="Issue title, description, traceback, and reproduction steps if repository is private or offline...",
        height=120,
    )

    submitted = st.form_submit_button("🚀 Launch Investigation", type="primary")

if submitted:
    target_issue = issue_input.strip() or repo_input.strip()
    if not target_issue and not pasted_issue:
        st.error("Please provide at least a GitHub issue URL, repository reference, or raw text.")
    else:
        inv_id = f"inv-{uuid.uuid4().hex[:8]}"

        # Resolve repository and issue number
        owner, repo_name, number = parse_issue_reference(target_issue)
        effective_repo = repo_input.strip()
        if not effective_repo and owner and repo_name:
            effective_repo = f"{owner}/{repo_name}"

        db = Database()
        new_inv = Investigation(
            id=inv_id,
            repo=effective_repo or "unknown",
            issue_number=number,
            issue_url=issue_input.strip() or target_issue,
            commit_sha=commit_sha.strip(),
            issue_summary=f"Triage queued for {effective_repo}#{number or ''}",
            final_status=InvestigationStatus.PENDING,
            mode=ExecutionMode(mode),
        )
        db.save_investigation(new_inv)

        # Spawn background worker process
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            subprocess.Popen(
                [sys.executable, "-m", "reprolens", "investigate", inv_id],
                cwd=str(Config.PROJECT_ROOT),
                creationflags=creationflags,
            )
            st.session_state["active_investigation_id"] = inv_id
            st.success(
                f"✅ Investigation `{inv_id}` started in background! Redirecting to Workspace..."
            )
            st.switch_page("ui/pages/workspace.py")
        except Exception as e:
            st.error(f"Failed to launch background worker: {e}")
