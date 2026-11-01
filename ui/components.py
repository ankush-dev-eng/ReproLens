"""Reusable Streamlit components for ReproLens."""

import streamlit as st

from reprolens.models import Attempt, Claim, ClaimKind, ExecutionOrigin, InvestigationStatus


def display_stage_timeline(status: InvestigationStatus):
    """Render a visual 5-stage progress indicator of the reproduction pipeline."""
    stages = [
        ("1. Issue Ingestion", "Extract title, body, tracebacks & symbols"),
        ("2. AST Indexing", "Deterministic symbol & callgraph retrieval"),
        ("3. Root Cause", "Formulate ranked hypotheses & verify citations"),
        ("4. Test Synthesis", "Generate minimal reproducer & AST security guard"),
        ("5. Execution & Classify", "Sandboxed execution, 3-run check & repair"),
    ]

    # Map status to stage completion
    # 0 = pending, 1 = analyzing (stages 1-3), 2 = reproducing (stage 4-5), 3 = finished
    current_step = 0
    if status == InvestigationStatus.PENDING:
        current_step = 0
    elif status == InvestigationStatus.ANALYZING:
        current_step = 2
    elif status == InvestigationStatus.REPRODUCING:
        current_step = 4
    elif status in (
        InvestigationStatus.REPRODUCED,
        InvestigationStatus.NOT_REPRODUCED,
        InvestigationStatus.INVALID_TEST,
        InvestigationStatus.ENVIRONMENT_ERROR,
        InvestigationStatus.EXECUTION_TIMEOUT,
        InvestigationStatus.PATCH_VALIDATED,
    ):
        current_step = 5

    cols = st.columns(len(stages))
    for idx, (title, desc) in enumerate(stages):
        step_num = idx + 1
        with cols[idx]:
            if step_num < current_step or current_step == 5:
                # Completed stage
                st.markdown(
                    f"""
                    <div style="background-color: #064E3B; border-top: 3px solid #10B981; padding: 0.6rem; border-radius: 0.375rem; min-height: 85px;">
                        <div style="color: #34D399; font-weight: bold; font-size: 0.85rem;">✅ {title}</div>
                        <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 0.25rem;">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif step_num == current_step:
                # Active stage
                st.markdown(
                    f"""
                    <div style="background-color: #1E3A8A; border-top: 3px solid #3B82F6; padding: 0.6rem; border-radius: 0.375rem; min-height: 85px;">
                        <div style="color: #93C5FD; font-weight: bold; font-size: 0.85rem;">⏳ {title}</div>
                        <div style="color: #E2E8F0; font-size: 0.75rem; margin-top: 0.25rem;">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                # Pending stage
                st.markdown(
                    f"""
                    <div style="background-color: #1E293B; border-top: 3px solid #475569; padding: 0.6rem; border-radius: 0.375rem; min-height: 85px;">
                        <div style="color: #64748B; font-weight: bold; font-size: 0.85rem;">⚪ {title}</div>
                        <div style="color: #475569; font-size: 0.75rem; margin-top: 0.25rem;">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def display_claim_card(claim: Claim):
    """Render a single claim with its verification state and citation."""
    kind_labels = {
        ClaimKind.HYPOTHESIS: ("💡 AI Hypothesis (Unverified probabilistic claim)", "#3B82F6"),
        ClaimKind.SOURCE_EVIDENCE: ("📄 Source Code Citation (AST-verified)", "#10B981"),
        ClaimKind.EXECUTION_EVIDENCE: ("🧪 Container Execution Evidence (Empirical)", "#8B5CF6"),
    }
    label, border_color = kind_labels.get(claim.kind, ("Claim", "#64748B"))

    with st.container():
        st.markdown(
            f"""
            <div style="border-left: 4px solid {border_color}; background-color: #0F172A; padding: 0.75rem 1rem; border-radius: 0 0.375rem 0.375rem 0; margin-bottom: 0.75rem;">
                <div style="font-size: 0.75rem; font-weight: 700; color: {border_color}; text-transform: uppercase; letter-spacing: 0.05em;">{label}</div>
                <div style="font-size: 0.95rem; margin-top: 0.35rem; color: #F1F5F9; line-height: 1.4;">{claim.text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if claim.source_ref:
            ref = claim.source_ref
            verified_badge = (
                "✅ Verified Citation (File & lines verified in worktree)"
                if ref.verified
                else "⚠️ Unverified Citation (File absent or lines do not match content)"
            )
            badge_color = "#34D399" if ref.verified else "#FBBF24"

            with st.expander(
                f"Source Ref: `{ref.path}:{ref.start_line}-{ref.end_line}` — {verified_badge}"
            ):
                st.markdown(
                    f"<div style='color: {badge_color}; font-size: 0.8rem; font-weight: 600; margin-bottom: 0.5rem;'>{verified_badge}</div>",
                    unsafe_allow_html=True,
                )
                if ref.snippet:
                    st.code(ref.snippet, language="python")


def display_attempt_card(attempt: Attempt):
    """Render a test execution attempt with output and provenance."""
    is_recorded = attempt.execution_origin == ExecutionOrigin.RECORDED
    origin_badge = (
        "⚠️ RECORDED RESULT — benchmark playback" if is_recorded else "⚡ LIVE CONTAINER EXECUTION"
    )
    badge_bg = "#78350F" if is_recorded else "#065F46"
    badge_fg = "#FBBF24" if is_recorded else "#34D399"

    status_color = "#34D399" if attempt.status.value == "REPRODUCED" else "#F87171"
    if attempt.status.value == "NOT_REPRODUCED":
        status_color = "#94A3B8"

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; background-color: #1E293B; padding: 0.6rem 0.85rem; border-radius: 0.375rem; margin-top: 0.75rem;">
            <div>
                <strong>Attempt #{attempt.attempt_no}</strong> &nbsp;—&nbsp;
                <span style="color: {status_color}; font-weight: bold;">{attempt.status.value}</span>
            </div>
            <span style="background-color: {badge_bg}; color: {badge_fg}; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.72rem; font-weight: bold; letter-spacing: 0.05em;">
                {origin_badge}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"View Test Source #{attempt.attempt_no}", expanded=False):
        st.code(attempt.test_source, language="python")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption(f"Exit Code: `{attempt.exit_code}`")
    with c2:
        st.caption(f"Execution Duration: `{attempt.duration_sec:.2f}s`")
    with c3:
        st.caption(f"Timestamp: `{attempt.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}`")

    if attempt.stdout or attempt.stderr:
        out_tab, err_tab = st.tabs(["Stdout (Test Runner)", "Stderr (Exceptions & Logs)"])
        with out_tab:
            if attempt.stdout:
                st.code(attempt.stdout[:8000], language="text")
            else:
                st.caption("No standard output captured.")
        with err_tab:
            if attempt.stderr:
                st.code(attempt.stderr[:8000], language="text")
            else:
                st.caption("No standard error captured.")
