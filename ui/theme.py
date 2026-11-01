"""UI Theme and styling constants for ReproLens."""

import streamlit as st

from reprolens.config import Config


def render_header():
    """Render top banner with execution mode indicator."""
    mode = Config.resolve_execution_mode()

    st.markdown(
        """
        <style>
        .repro-badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 0.375rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .badge-live { background-color: #065F46; color: #34D399; }
        .badge-demo { background-color: #78350F; color: #FBBF24; }
        .badge-error { background-color: #7F1D1D; color: #F87171; }
        .badge-info { background-color: #1E3A8A; color: #60A5FA; }
        .evidence-card {
            border: 1px solid #334155;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 0.75rem;
            background-color: #1E293B;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            "### 🔬 **ReproLens** &nbsp; <span style='font-size: 0.9rem; color: #94A3B8; font-weight: normal;'>AI-Powered GitHub Issue Reproduction Engine</span>",
            unsafe_allow_html=True,
        )
    with col2:
        if mode == "docker":
            st.markdown(
                "<div style='text-align: right;'><span class='repro-badge badge-live'>⚡ Docker Sandbox Active</span></div>",
                unsafe_allow_html=True,
            )
        elif mode == "remote":
            st.markdown(
                "<div style='text-align: right;'><span class='repro-badge badge-info'>🌐 Remote Sandbox Active</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='text-align: right;'><span class='repro-badge badge-demo'>⚠️ Demo Mode (Recorded Evidence Only)</span></div>",
                unsafe_allow_html=True,
            )

    if mode == "demo":
        st.info(
            "**DEMO MODE ACTIVE:** No local Docker daemon was detected or cloud environment is active. "
            "Execution is restricted to pre-recorded benchmark evidence to guarantee safety and reproducibility. "
            "Arbitrary repository code execution is disabled."
        )


def render_status_badge(status: str) -> str:
    """Return HTML snippet for a status badge."""
    color_map = {
        "REPRODUCED": ("#065F46", "#34D399"),
        "PATCH_VALIDATED": ("#065F46", "#34D399"),
        "NOT_REPRODUCED": ("#475569", "#CBD5E1"),
        "INVALID_TEST": ("#78350F", "#FBBF24"),
        "ENVIRONMENT_ERROR": ("#7F1D1D", "#F87171"),
        "EXECUTION_TIMEOUT": ("#7F1D1D", "#F87171"),
        "ANALYZING": ("#1E3A8A", "#60A5FA"),
        "REPRODUCING": ("#1E3A8A", "#60A5FA"),
        "PENDING": ("#334155", "#94A3B8"),
    }
    bg, fg = color_map.get(status, ("#334155", "#94A3B8"))
    return f"<span style='background-color: {bg}; color: {fg}; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 600;'>{status}</span>"
