"""Git History and Bisect page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.theme import render_header

render_header()

st.title("Git History & Automated Bisect")
st.markdown(
    "Automated bisection to locate the regression-introducing commit using isolated worktrees."
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

runs = db.list_bisect_runs(selected_id)

if not runs:
    st.info("No bisect runs performed for this investigation yet.")
else:
    st.subheader("Tested Commit Timeline")
    for r in runs:
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            st.code(r.commit_sha[:10])
        with col2:
            st.write(f"Status: **{r.status}**")
        with col3:
            st.caption(
                f"Passed: {r.pass_count}/{r.run_count} | Failed: {r.fail_count}/{r.run_count}"
            )
        st.divider()
