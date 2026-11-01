"""Reusable Streamlit components for ReproLens."""

import streamlit as st

from reprolens.models import Attempt, Claim, ClaimKind, ExecutionOrigin


def display_claim_card(claim: Claim):
    """Render a single claim with its verification state and citation."""
    kind_labels = {
        ClaimKind.HYPOTHESIS: ("💡 Hypothesis (Unverified AI Analysis)", "#3B82F6"),
        ClaimKind.SOURCE_EVIDENCE: ("📄 Source Evidence", "#10B981"),
        ClaimKind.EXECUTION_EVIDENCE: ("🧪 Execution Evidence", "#8B5CF6"),
    }
    label, border_color = kind_labels.get(claim.kind, ("Claim", "#64748B"))

    with st.container():
        st.markdown(
            f"""
            <div style="border-left: 4px solid {border_color}; padding-left: 0.75rem; margin-bottom: 0.75rem;">
                <div style="font-size: 0.8rem; font-weight: 600; color: #94A3B8;">{label}</div>
                <div style="font-size: 0.95rem; margin-top: 0.2rem;">{claim.text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if claim.source_ref:
            ref = claim.source_ref
            verified_badge = (
                "✅ Verified Citation"
                if ref.verified
                else "⚠️ Unverified Citation (Line/text mismatch or file absent)"
            )
            badge_color = "#34D399" if ref.verified else "#FBBF24"

            with st.expander(
                f"Reference: `{ref.path}:{ref.start_line}-{ref.end_line}` — {verified_badge}"
            ):
                st.markdown(
                    f"<span style='color: {badge_color}; font-size: 0.8rem; font-weight: bold;'>{verified_badge}</span>",
                    unsafe_allow_html=True,
                )
                if ref.snippet:
                    st.code(ref.snippet, language="python")


def display_attempt_card(attempt: Attempt):
    """Render a test execution attempt with output and provenance."""
    is_recorded = attempt.execution_origin == ExecutionOrigin.RECORDED
    origin_badge = (
        "⚠️ RECORDED RESULT — not a live execution" if is_recorded else "⚡ LIVE EXECUTION RESULT"
    )
    badge_bg = "#78350F" if is_recorded else "#065F46"
    badge_fg = "#FBBF24" if is_recorded else "#34D399"

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
            <strong>Attempt #{attempt.attempt_no} — Status: <code>{attempt.status.value}</code></strong>
            <span style="background-color: {badge_bg}; color: {badge_fg}; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: bold;">
                {origin_badge}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"View Test Source #{attempt.attempt_no}"):
        st.code(attempt.test_source, language="python")

    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"Exit Code: `{attempt.exit_code}` | Duration: `{attempt.duration_sec:.2f}s`")
    with col2:
        st.caption(f"Captured: {attempt.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    if attempt.stdout:
        st.markdown("**Stdout:**")
        st.code(attempt.stdout[:4000], language="text")
    if attempt.stderr:
        st.markdown("**Stderr:**")
        st.code(attempt.stderr[:4000], language="text")
