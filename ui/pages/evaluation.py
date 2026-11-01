"""Benchmark Evaluation page for ReproLens."""

import streamlit as st

from reprolens.db import Database
from ui.theme import render_header

render_header()

st.title("Benchmark Evaluation")
st.markdown("Audited evaluation metrics across the curated benchmark suite.")

db = Database()
eval_runs = db.list_eval_runs()

if not eval_runs:
    st.info(
        "No benchmark evaluation runs recorded yet. Run `python -m reprolens evaluate` to execute."
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
