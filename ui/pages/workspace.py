"""Investigation Workspace page for ReproLens with live execution polling."""

import streamlit as st

from reprolens.db import Database
from reprolens.models import InvestigationStatus
from ui.components import (
    display_attempt_card,
    display_claim_card,
    display_stage_timeline,
)
from ui.theme import render_header, render_status_badge

render_header()

db = Database()
investigations = db.list_investigations()

if not investigations:
    st.info("No investigations found. Click **New Investigation** in the sidebar to start one.")
    st.stop()

# Selector for active investigation
inv_ids = [inv.id for inv in investigations]
default_index = 0
if (
    "active_investigation_id" in st.session_state
    and st.session_state["active_investigation_id"] in inv_ids
):
    default_index = inv_ids.index(st.session_state["active_investigation_id"])

col_sel, col_ref = st.columns([4, 1])
with col_sel:
    selected_id = st.selectbox(
        "Select Active Investigation",
        inv_ids,
        index=default_index,
        format_func=lambda i_id: f"{i_id} — {next((i.repo + ' #' + str(i.issue_number or '') for i in investigations if i.id == i_id), i_id)}",
    )
    st.session_state["active_investigation_id"] = selected_id

with col_ref:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

inv = db.get_investigation(selected_id)
if not inv:
    st.error("Selected investigation not found.")
    st.stop()

# Determine if investigation is currently active for live polling
is_active = inv.final_status in (
    InvestigationStatus.PENDING,
    InvestigationStatus.ANALYZING,
    InvestigationStatus.REPRODUCING,
)


@st.fragment(run_every=2.0 if is_active else None)
def render_live_workspace(investigation_id: str):
    """Render workspace with auto-refresh while background task executes."""
    current_db = Database()
    cur_inv = current_db.get_investigation(investigation_id)
    if not cur_inv:
        return

    # Header Card
    c_title, c_badge = st.columns([3, 1])
    with c_title:
        st.subheader(f"{cur_inv.repo} #{cur_inv.issue_number or ''}")
        st.caption(
            f"ID: `{cur_inv.id}` | Mode: `{cur_inv.mode.value}` | "
            f"Commit: `{cur_inv.commit_sha[:10] if cur_inv.commit_sha else 'Auto-resolved'}`"
        )
    with c_badge:
        st.markdown(
            f"<div style='text-align: right; padding-top: 0.5rem;'>{render_status_badge(cur_inv.final_status.value)}</div>",
            unsafe_allow_html=True,
        )
        if cur_inv.duration_sec > 0:
            st.markdown(
                f"<div style='text-align: right; font-size: 0.8rem; color: #94A3B8;'>Elapsed: <b>{cur_inv.duration_sec:.1f}s</b></div>",
                unsafe_allow_html=True,
            )

    # 5-Stage Pipeline Progress Indicator
    st.markdown("#### Reproduction Pipeline Stage")
    display_stage_timeline(cur_inv.final_status)
    st.markdown("")

    # Status Callouts
    if cur_inv.final_status == InvestigationStatus.PENDING:
        st.info("⏳ **Queued:** Background worker starting...")
    elif cur_inv.final_status == InvestigationStatus.ANALYZING:
        st.info(
            "🔍 **Analyzing:** AST indexing target codebase and retrieving candidate symbols..."
        )
    elif cur_inv.final_status == InvestigationStatus.REPRODUCING:
        st.info(
            "🧪 **Reproducing:** Synthesizing minimal test and running sandboxed execution attempts..."
        )
    elif cur_inv.final_status == InvestigationStatus.REPRODUCED:
        st.success(
            "🎯 **ISSUE REPRODUCED:** Minimal reproduction test confirmed failure symptom against buggy commit!"
        )
    elif cur_inv.final_status == InvestigationStatus.NOT_REPRODUCED:
        st.info(
            "🛡️ **HONEST REFUSAL (NOT REPRODUCED):** Generated test passed 3/3 times. "
            "The reported bug did not manifest at this revision or requires additional environmental factors."
        )
    elif cur_inv.final_status == InvestigationStatus.INVALID_TEST:
        st.warning(
            "⚠️ **INVALID TEST:** Synthesized test was rejected by AST security guards or failed sanity checks."
        )
    elif cur_inv.final_status == InvestigationStatus.ENVIRONMENT_ERROR:
        st.error(
            f"❌ **ENVIRONMENT ERROR:** Sandboxed container execution or setup failed: {cur_inv.issue_summary}"
        )

    claims = current_db.list_claims(cur_inv.id)
    attempts = current_db.list_attempts(cur_inv.id)

    # Main Content Tabs
    tab_test, tab_exec, tab_claims, tab_context = st.tabs(
        [
            "🔬 Minimal Reproducer Test",
            f"🧪 Execution Evidence ({len(attempts)})",
            f"📜 Hypotheses & Citations ({len(claims)})",
            "📄 Issue Context",
        ]
    )

    with tab_test:
        if not attempts:
            st.info("No test generated yet. Analysis in progress...")
        else:
            latest_attempt = attempts[-1]
            st.markdown(
                f"**Reproducer Script** (Attempt #{latest_attempt.attempt_no} — Status: `{latest_attempt.status.value}`)"
            )
            st.code(latest_attempt.test_source, language="python")

            c_down, c_patch = st.columns([2, 2])
            with c_down:
                st.download_button(
                    label="📥 Download Reproducer Script (.py)",
                    data=latest_attempt.test_source,
                    file_name=f"test_repro_{cur_inv.id}.py",
                    mime="text/x-python",
                    use_container_width=True,
                )
            with c_patch:
                if st.button("🩹 Open in Patch Validator", use_container_width=True):
                    st.switch_page("ui/pages/repro_patch.py")

    with tab_exec:
        if not attempts:
            st.info("No sandbox execution attempts recorded yet.")
        else:
            for attempt in attempts:
                display_attempt_card(attempt)

    with tab_claims:
        if not claims:
            st.info("No hypotheses or citations recorded yet.")
        else:
            for claim in claims:
                display_claim_card(claim)

    with tab_context:
        st.markdown(f"**Target Issue:** [{cur_inv.issue_url}]({cur_inv.issue_url})")
        if cur_inv.issue_summary:
            st.markdown(f"**Summary:** {cur_inv.issue_summary}")
        if cur_inv.commit_sha:
            st.code(f"Commit SHA: {cur_inv.commit_sha}", language="text")


render_live_workspace(selected_id)
