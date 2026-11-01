"""New Investigation page for ReproLens."""

import uuid

import streamlit as st

from reprolens.config import Config
from reprolens.db import Database
from reprolens.models import ExecutionMode, Investigation, InvestigationStatus
from ui.theme import render_header

render_header()

st.title("Start New Investigation")
st.markdown("Provide a GitHub issue URL or paste raw issue details to initiate triage.")

mode = Config.resolve_execution_mode()
if mode == "demo":
    st.warning(
        "⚠️ **Demo Mode Active:** New live repository executions are disabled because no local Docker daemon is running. "
        "You can inspect existing recorded benchmark cases or connect Docker to run live investigations."
    )

with st.form("new_investigation_form"):
    repo_url = st.text_input(
        "Target Repository URL or Owner/Repo",
        placeholder="https://github.com/psf/requests or psf/requests",
        help="Target public repository on GitHub",
    )
    issue_input = st.text_input(
        "GitHub Issue URL or Number",
        placeholder="https://github.com/psf/requests/issues/1234 or #1234",
    )
    commit_sha = st.text_input(
        "Base Commit SHA (Optional)",
        placeholder="Leave blank to use issue creation date commit",
    )
    pasted_issue = st.text_area(
        "Or Paste Raw Issue Text (Optional)",
        placeholder="Issue title, description, traceback, and expected vs actual behavior...",
        height=150,
    )

    submitted = st.form_submit_button("Start Investigation", type="primary")

if submitted:
    if not repo_url and not issue_input and not pasted_issue:
        st.error("Please provide at least a GitHub issue URL or raw issue text.")
    else:
        inv_id = f"inv-{uuid.uuid4().hex[:8]}"
        db = Database()
        new_inv = Investigation(
            id=inv_id,
            repo=repo_url or "unknown",
            issue_url=issue_input or "pasted",
            commit_sha=commit_sha.strip(),
            issue_summary="Queued for analysis",
            final_status=InvestigationStatus.PENDING,
            mode=ExecutionMode(mode),
        )
        db.save_investigation(new_inv)
        st.session_state["active_investigation_id"] = inv_id
        st.success(f"Investigation initialized: `{inv_id}`. Redirecting to workspace...")
        st.switch_page("ui/pages/workspace.py")
