"""Tests for Streamlit application loading and headless startup."""

from streamlit.testing.v1 import AppTest


def test_main_app_loads():
    at = AppTest.from_file("main.py", default_timeout=10)
    at.run()
    assert not at.exception


def test_pages_load():
    for page in [
        "ui/pages/dashboard.py",
        "ui/pages/new_investigation.py",
        "ui/pages/workspace.py",
        "ui/pages/ledger.py",
        "ui/pages/repro_patch.py",
        "ui/pages/git_history.py",
        "ui/pages/evaluation.py",
    ]:
        at = AppTest.from_file(page, default_timeout=10)
        at.run()
        assert not at.exception, f"Exception loading {page}: {at.exception}"
