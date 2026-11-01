"""Git History and Bisect page for ReproLens."""

import streamlit as st

from reprolens.bisect import GitBisectEngine
from reprolens.db import Database
from reprolens.repo import RepositoryManager
from ui.theme import render_header

render_header()

st.title("Git History & Automated Bisect")
st.markdown(
    "Automated bisection to find the regression-introducing commit using isolated git worktrees."
)

db = Database()
investigations = db.list_investigations()

if not investigations:
    st.info("No investigations recorded. Start one in the 'New Investigation' page.")
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

inv = db.get_investigation(selected_id)
attempts = db.list_attempts(selected_id)
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

col_act, _ = st.columns([2, 2])
with col_act:
    if st.button("🌿 Launch Automated Bisect", type="primary", use_container_width=True):
        if not attempts:
            st.error("No minimal reproducer test available for this investigation yet.")
        else:
            with st.spinner("Executing bisection search in isolated worktrees..."):
                try:
                    repo_mgr = RepositoryManager()
                    repo_dir = repo_mgr.get_repo_cache_dir(inv.repo)
                    if not repo_dir.exists():
                        repo_dir = repo_mgr.clone_or_fetch(inv.repo)

                    engine = GitBisectEngine(repo_dir=repo_dir, db=db)
                    result = engine.bisect(
                        investigation_id=inv.id,
                        buggy_commit=inv.commit_sha or "HEAD",
                        test_source=attempts[-1].test_source,
                    )
                    st.success(f"🎯 Culprit Commit Isolated: `{result.culprit_commit}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Bisect failed: {e}")

if not runs:
    st.info(f"No automated bisect runs logged for investigation `{selected_id}` yet.")
else:
    st.subheader(f"Tested Commit Timeline ({len(runs)} revisions)")
    for r in runs:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            status_color = (
                "#34D399" if r.status == "good" else ("#F87171" if r.status == "bad" else "#FBBF24")
            )
            with col1:
                st.code(r.commit_sha[:10], language="text")
            with col2:
                st.markdown(
                    f"Status: <b style='color: {status_color};'>{r.status.upper()}</b>",
                    unsafe_allow_html=True,
                )
            with col3:
                st.caption(
                    f"Passed: {r.pass_count}/{r.run_count} | Failed: {r.fail_count}/{r.run_count}"
                )
