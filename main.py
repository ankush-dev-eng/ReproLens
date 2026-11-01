"""ReproLens Streamlit Application Entrypoint."""

import streamlit as st

st.set_page_config(
    page_title="ReproLens: AI Issue Reproduction Engine",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("ui/pages/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("ui/pages/new_investigation.py", title="New Investigation", icon="➕"),
    st.Page("ui/pages/workspace.py", title="Investigation Workspace", icon="🔬"),
    st.Page("ui/pages/ledger.py", title="Evidence Ledger", icon="📜"),
    st.Page("ui/pages/repro_patch.py", title="Reproduction & Patch", icon="🩹"),
    st.Page("ui/pages/git_history.py", title="Git History & Bisect", icon="🌿"),
    st.Page("ui/pages/evaluation.py", title="Benchmark Evaluation", icon="📈"),
]

pg = st.navigation(pages)
pg.run()
