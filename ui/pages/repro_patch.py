"""Reproduction & Patch Validation page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.theme import render_header

render_header()

st.title("Reproduction & Patch Validation")
st.markdown(
    "Inspect the final verified test case and validate candidate patches against the baseline."
)

db = Database()
investigations = db.list_investigations()

if not investigations:
    st.info("No investigations recorded.")
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

attempts = db.list_attempts(selected_id)
reproduced_attempts = [a for a in attempts if a.status.value == "REPRODUCED"]

if not attempts:
    st.info("No attempts logged for this investigation.")
else:
    st.subheader("Latest Reproduction Test")
    latest = attempts[-1]
    st.code(latest.test_source, language="python")

    st.subheader("Patch Validation")
    st.info(
        "Candidate patches are validated by checking that the reproduction test fails before the patch, "
        "passes after the patch (3/3 runs), and does not introduce regressions into the existing test suite."
    )
