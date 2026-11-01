"""Investigation Workspace page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.components import display_attempt_card, display_claim_card
from ui.theme import render_header, render_status_badge

render_header()

db = Database()
investigations = db.list_investigations()

if not investigations:
    st.info("No investigations found. Start one in the 'New Investigation' page.")
    st.stop()

# Selector for active investigation
inv_ids = [inv.id for inv in investigations]
default_index = 0
if (
    "active_investigation_id" in st.session_state
    and st.session_state["active_investigation_id"] in inv_ids
):
    default_index = inv_ids.index(st.session_state["active_investigation_id"])

selected_id = st.selectbox("Select Investigation", inv_ids, index=default_index)
st.session_state["active_investigation_id"] = selected_id
inv = db.get_investigation(selected_id)

if not inv:
    st.error("Selected investigation not found.")
    st.stop()

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader(f"Workspace: {inv.repo} #{inv.issue_number or ''}")
    st.caption(f"ID: `{inv.id}` | Mode: `{inv.mode.value}` | URL: {inv.issue_url}")
with col2:
    st.markdown(
        f"<div style='text-align: right; padding-top: 1rem;'>{render_status_badge(inv.final_status.value)}</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

tab_claims, tab_attempts = st.tabs(["Ledger & Hypotheses", "Reproduction Attempts"])

with tab_claims:
    claims = db.list_claims(inv.id)
    if not claims:
        st.info("No hypotheses or evidence claims registered for this investigation yet.")
    else:
        for claim in claims:
            display_claim_card(claim)

with tab_attempts:
    attempts = db.list_attempts(inv.id)
    if not attempts:
        st.info("No execution attempts recorded for this investigation yet.")
    else:
        for attempt in attempts:
            display_attempt_card(attempt)
            st.divider()
