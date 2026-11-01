"""Dashboard page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.theme import render_header, render_status_badge

render_header()

st.title("Investigation Dashboard")
st.markdown(
    "Overview of autonomous issue reproduction runs, real-time triage state, and audit metrics."
)

db = Database()
investigations = db.list_investigations()

col1, col2, col3, col4, col5 = st.columns(5)

total_count = len(investigations)
reproduced_count = sum(
    1 for i in investigations if i.final_status.value in ("REPRODUCED", "PATCH_VALIDATED")
)
not_reproduced_count = sum(1 for i in investigations if i.final_status.value == "NOT_REPRODUCED")
failed_count = sum(
    1
    for i in investigations
    if i.final_status.value in ("INVALID_TEST", "ENVIRONMENT_ERROR", "EXECUTION_TIMEOUT")
)
durations = [i.duration_sec for i in investigations if i.duration_sec > 0]
avg_duration = sum(durations) / len(durations) if durations else 0.0

with col1:
    st.metric("Total Runs", total_count)
with col2:
    st.metric("Reproduced (Verified)", reproduced_count)
with col3:
    st.metric("Honest Refusals", not_reproduced_count)
with col4:
    st.metric("Environment / Invalid", failed_count)
with col5:
    st.metric("Avg Duration", f"{avg_duration:.1f}s")

st.markdown("---")

# Quick Launch Box
c_quick, c_action = st.columns([3, 1])
with c_quick:
    st.subheader("⚡ Quick Launch Benchmark Triage")
    st.caption("Start immediate autonomous triage on verified benchmark cases:")
with c_action:
    st.write("")
    if st.button("➕ Custom Investigation", type="primary", use_container_width=True):
        st.switch_page("ui/pages/new_investigation.py")

col_b1, col_b2, col_b3 = st.columns(3)
with col_b1, st.container(border=True):
    st.markdown("**pallets/click #3019**")
    st.caption("Prompt appends space when prompt_suffix=''")
    if st.button("Triage Click #3019", key="btn_tri_click"):
        st.session_state["field_repo"] = "pallets/click"
        st.session_state["field_issue"] = "https://github.com/pallets/click/issues/3019"
        st.session_state["field_commit"] = "27aaed3fe5bcd6adedd6e91de234914af9859cf1"
        st.switch_page("ui/pages/new_investigation.py")

with col_b2, st.container(border=True):
    st.markdown("**marshmallow #1842**")
    st.caption("Schema validation regression on nested missing fields")
    if st.button("Triage Marshmallow #1842", key="btn_tri_mm"):
        st.session_state["field_repo"] = "marshmallow-code/marshmallow"
        st.session_state["field_issue"] = (
            "https://github.com/marshmallow-code/marshmallow/issues/1842"
        )
        st.session_state["field_commit"] = ""
        st.switch_page("ui/pages/new_investigation.py")

with col_b3, st.container(border=True):
    st.markdown("**psf/requests #4175**")
    st.caption("Header encoding bug with specific HTTP methods")
    if st.button("Triage Requests #4175", key="btn_tri_req"):
        st.session_state["field_repo"] = "psf/requests"
        st.session_state["field_issue"] = "https://github.com/psf/requests/issues/4175"
        st.session_state["field_commit"] = ""
        st.switch_page("ui/pages/new_investigation.py")

st.markdown("---")
st.subheader("Recent Investigations")

if not investigations:
    st.info(
        "No investigations recorded yet. Click **New Investigation** or choose a benchmark case above."
    )
else:
    for inv in investigations:
        with st.container():
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
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
                st.caption(f"Mode: `{inv.mode.value}` | `{inv.duration_sec:.1f}s`")
            with c4:
                if st.button("Open Workspace", key=f"btn_open_{inv.id}", use_container_width=True):
                    st.session_state["active_investigation_id"] = inv.id
                    st.switch_page("ui/pages/workspace.py")
            st.divider()
