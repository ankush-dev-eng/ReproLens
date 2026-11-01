"""Reproduction & Patch Validation page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from reprolens.models import InvestigationStatus
from reprolens.patching import PatchEngine
from reprolens.repo import RepositoryManager
from ui.theme import render_header

render_header()

st.title("Reproduction & Patch Validation")
st.markdown(
    "Verify the minimal reproducer script and execute 4-step patch validation against candidate fixes."
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

if not attempts:
    st.info("No test attempts logged for this investigation yet.")
    st.stop()

reproduced_attempts = [a for a in attempts if a.status.value == "REPRODUCED"]
latest = reproduced_attempts[-1] if reproduced_attempts else attempts[-1]

st.subheader("1. Minimal Reproducer Test Script")
st.caption(
    f"Attempt #{latest.attempt_no} — Status: `{latest.status.value}` | Duration: `{latest.duration_sec:.2f}s`"
)

st.code(latest.test_source, language="python")

st.download_button(
    label="📥 Download Standalone Reproducer (.py)",
    data=latest.test_source,
    file_name=f"test_repro_{selected_id}.py",
    mime="text/x-python",
    use_container_width=True,
)

st.markdown("---")
st.subheader("2. Patch Validation Pipeline")
st.markdown(
    """
    To guarantee mathematical rigor and prevent fake fixes, candidate patches must pass a **4-gate validation**:
    1. **Baseline Invariant**: Minimal test must *fail* on the target revision with `EXPECTED_SYMPTOM`.
    2. **Patch Application**: Unified diff applies cleanly with `git apply --check`.
    3. **Pass Consistency**: Minimal test must *pass* 3/3 consecutive times after the patch is applied.
    4. **Zero Regressions**: Running the existing repository test suite must produce 0 new failures.
    """
)

# Default patch for Click 3019
default_diff = """--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -140,4 +140,6 @@ def prompt(
     if prompt_suffix:
         return f"{text}{prompt_suffix} "
-    return f"{text} "
+    if prompt_suffix == "":
+        return text
+    return f"{text} "
"""

diff_input = st.text_area(
    "Candidate Fix Patch (Unified Diff)",
    value=default_diff,
    height=160,
    help="Unified diff to apply with git apply against the target revision",
)

if st.button("🧪 Execute 4-Gate Patch Validation", type="primary"):
    with st.spinner("Executing 4-gate patch verification in isolated worktree..."):
        repo_mgr = RepositoryManager()
        repo_dir = repo_mgr.get_repo_cache_dir(inv.repo)
        if not repo_dir.exists():
            repo_dir = repo_mgr.clone_or_fetch(inv.repo)

        engine = PatchEngine(db=db, repo_mgr=repo_mgr)
        val_res = engine.validate_patch(
            investigation_id=inv.id,
            repo_dir=repo_dir,
            base_commit=inv.commit_sha or "HEAD",
            test_source=latest.test_source,
            diff=diff_input,
        )

        if val_res.gate1_baseline_failed:
            st.success("✅ Gate 1 Passed: Reproducer fails on baseline commit (1/1)")
        else:
            st.error("❌ Gate 1 Failed: Reproducer did not fail on baseline")

        if val_res.gate2_patch_applied:
            st.success("✅ Gate 2 Passed: Patch applied cleanly without conflicts")
        else:
            st.error("❌ Gate 2 Failed: Patch application rejected")

        if val_res.gate3_post_patch_passed:
            st.success("✅ Gate 3 Passed: Reproducer passes 3/3 times after patch")
        else:
            st.error("❌ Gate 3 Failed: Reproducer did not pass 3/3 times after patch")

        if val_res.gate4_regression_clean:
            st.success("✅ Gate 4 Passed: 0 regressions across existing test suite")
        else:
            st.error("❌ Gate 4 Failed: Regressions detected")

        if val_res.final_status == InvestigationStatus.PATCH_VALIDATED:
            st.balloons()
            st.success("🎉 **VERIFIED**: Investigation status promoted to `PATCH_VALIDATED`!")
        else:
            st.warning(f"Outcome: {val_res.final_status.value} — {val_res.details}")
