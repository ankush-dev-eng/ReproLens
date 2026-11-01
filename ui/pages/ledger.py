"""Evidence Ledger page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from reprolens.models import ClaimKind
from ui.components import display_claim_card
from ui.theme import render_header

render_header()

st.title("Evidence Ledger")
st.markdown(
    "Auditable separation of unverified AI hypotheses from verified source citations and executed container evidence."
)

db = Database()
investigations = db.list_investigations()

if not investigations:
    st.info("No investigations in database.")
    st.stop()

inv_ids = [inv.id for inv in investigations]
default_idx = 0
if (
    "active_investigation_id" in st.session_state
    and st.session_state["active_investigation_id"] in inv_ids
):
    default_idx = inv_ids.index(st.session_state["active_investigation_id"])

selected_id = st.selectbox("Select Investigation", inv_ids, index=default_idx)
st.session_state["active_investigation_id"] = selected_id

claims = db.list_claims(selected_id)

col1, col2, col3 = st.columns(3)
hypotheses = [c for c in claims if c.kind == ClaimKind.HYPOTHESIS]
source_ev = [c for c in claims if c.kind == ClaimKind.SOURCE_EVIDENCE]
exec_ev = [c for c in claims if c.kind == ClaimKind.EXECUTION_EVIDENCE]

with col1:
    st.metric("Hypotheses (Unverified)", len(hypotheses))
with col2:
    st.metric("Source Citations", len(source_ev))
with col3:
    st.metric("Execution Evidence", len(exec_ev))

st.markdown("---")

filter_kind = st.radio(
    "Filter by Evidence Type",
    ["All", "Hypotheses Only", "Source Evidence Only", "Execution Evidence Only"],
    horizontal=True,
)

for claim in claims:
    if filter_kind == "Hypotheses Only" and claim.kind != ClaimKind.HYPOTHESIS:
        continue
    if filter_kind == "Source Evidence Only" and claim.kind != ClaimKind.SOURCE_EVIDENCE:
        continue
    if filter_kind == "Execution Evidence Only" and claim.kind != ClaimKind.EXECUTION_EVIDENCE:
        continue

    display_claim_card(claim)
