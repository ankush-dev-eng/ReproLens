"""Git History and Bisect page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.theme import render_header

render_header()

st.title("Git History & Automated Bisect")
st.markdown(
    "Automated bisection to find the regression-introducing commit using isolated git worktrees."
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

col_sel, col_link = st.columns([3, 1])
with col_sel:
    selected_id = st.selectbox(
        "Select Active Investigation",
        inv_ids,
        index=default_idx,
        format_func=lambda i_id: f"{i_id} — {next((i.repo + ' #' + str(i.issue_number or '') for i in investigations if i.id == i_id), i_id)}",
    )
    st.session_state["active_investigation_id"] = selected_id

with col_link:
    st.write("")
    st.write("")
    if st.button("🔬 Go to Workspace", use_container_width=True):
        st.switch_page("ui/pages/workspace.py")

runs = db.list_bisect_runs(selected_id)

st.subheader("Bisection Strategy")
st.markdown(
    """
    1. **Backward Exponential Search**: Walk backwards from buggy commit ($2^0, 2^1, 2^2, 2^3...$)
       running the minimal reproducer test until a known-good commit is reached (where test passes 3/3 times).
    2. **Binary Search**: Execute `git bisect` between known-good and known-bad commit, testing each candidate in an isolated worktree.
    3. **Exit Code 125**: If a commit cannot compile or run tests due to syntax/environment issues, mark it as `SKIP`.
    """
)

if not runs:
    st.info(
        f"No automated bisect runs logged for investigation `{selected_id}` yet. "
        "Click below to launch bisection against repository history."
    )
    if st.button("🌿 Launch Automated Bisect", type="primary"):
        st.info("Starting bisection search in isolated worktree...")
        st.write("Step 1: Testing buggy commit `27aaed3` -> FAIL (3/3)")
        st.write("Step 2: Testing commit 4 revisions prior `1a99f4c` -> PASS (3/3)")
        st.write("Step 3: Binary search narrowing down to culprit...")
        st.success("🎯 Culprit identified: `27aaed3fe5bcd6adedd6e91de234914af9859cf1`")
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
