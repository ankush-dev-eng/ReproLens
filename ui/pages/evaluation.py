"""Benchmark Evaluation page for ReproLens."""

import streamlit as st
import yaml

from reprolens.config import Config
from reprolens.db import Database
from ui.theme import render_header

render_header()

st.title("Benchmark Evaluation Suite")
st.markdown(
    "Audited evaluation metrics across curated historical Python bug benchmarks. "
    "Every metric reflects verifiable test execution — no synthetic or fabricated claims."
)

db = Database()
eval_runs = db.list_eval_runs()

if not eval_runs:
    st.info(
        "No multi-case evaluation run recorded yet. You can launch evaluation from the CLI: "
        "`python -m reprolens evaluate` or view individual investigation results in the Dashboard."
    )
else:
    latest = eval_runs[0]
    st.subheader(f"Latest Run: {latest.model_id} ({latest.run_date.strftime('%Y-%m-%d %H:%M')})")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cases", latest.total_cases)
    with col2:
        st.metric("Reproduction Rate", f"{latest.reproduction_rate * 100:.1f}%")
    with col3:
        st.metric("Fail-to-Pass Rate", f"{latest.fail_to_pass_rate * 100:.1f}%")
    with col4:
        st.metric("False Reproduction", f"{latest.false_reproduction_rate * 100:.1f}%")

    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Invalid Test Rate", f"{latest.invalid_test_rate * 100:.1f}%")
    with col6:
        st.metric("Env Error Rate", f"{latest.env_error_rate * 100:.1f}%")
    with col7:
        cost_str = f"${latest.total_cost_usd:.4f}" if latest.total_cost_usd is not None else "N/A"
        st.metric("Total Tokens / Cost", f"{latest.total_tokens:,} ({cost_str})")

st.markdown("---")
st.subheader("Curated Benchmark Suite (manifest.yaml)")

manifest_path = Config.PROJECT_ROOT / "benchmark" / "manifest.yaml"
if manifest_path.exists():
    try:
        manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        cases = manifest_data.get("cases", [])
        st.caption(
            f"Curated benchmark contains **{len(cases)}** verified real-world issues from open-source Python libraries."
        )

        for case in cases:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**{case.get('id')}** — `{case.get('repo_url')}`")
                    st.caption(case.get("provenance_notes", ""))
                with c2:
                    st.write(f"Target: **{case.get('expected_result')}**")
                    st.caption(f"Symptom: `{case.get('expected_symptom_category')}`")
                with c3:
                    st.code(f"Commit: {case.get('base_commit', '')[:10]}", language="text")
    except Exception as e:
        st.error(f"Failed to read benchmark manifest: {e}")
