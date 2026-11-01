"""Dashboard page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.theme import render_header, render_status_badge

render_header()

st.title("Investigation Dashboard")
st.markdown("Overview of all issue reproduction runs and active triage state.")

db = Database()
investigations = db.list_investigations()

col1, col2, col3, col4 = st.columns(4)

total_count = len(investigations)
reproduced_count = sum(1 for i in investigations if i.final_status.value == "REPRODUCED")
not_reproduced_count = sum(1 for i in investigations if i.final_status.value == "NOT_REPRODUCED")
failed_count = sum(
    1
    for i in investigations
    if i.final_status.value in ("INVALID_TEST", "ENVIRONMENT_ERROR", "EXECUTION_TIMEOUT")
)

with col1:
    st.metric("Total Investigations", total_count)
with col2:
    st.metric("Reproduced (Verified)", reproduced_count)
with col3:
    st.metric("Not Reproduced (Honest Refusal)", not_reproduced_count)
with col4:
    st.metric("Environmental / Invalid", failed_count)

st.markdown("---")
st.subheader("Recent Investigations")

if not investigations:
    st.info(
        "No investigations recorded yet. Click **New Investigation** in the sidebar to start triaging an issue."
    )
else:
    for inv in investigations:
        with st.container():
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            with c1:
                st.markdown(
                    f"**{inv.repo}** [#{inv.issue_number}]({inv.issue_url})"
                    if inv.issue_number
                    else f"**{inv.repo}**"
                )
                if inv.issue_summary:
                    st.caption(inv.issue_summary[:120])
            with c2:
                st.markdown(render_status_badge(inv.final_status.value), unsafe_allow_html=True)
            with c3:
                st.caption(f"Mode: `{inv.mode.value}` | Duration: `{inv.duration_sec:.1f}s`")
            with c4:
                if st.button("Open Workspace", key=f"btn_open_{inv.id}"):
                    st.session_state["active_investigation_id"] = inv.id
                    st.switch_page("ui/pages/workspace.py")
            st.divider()
