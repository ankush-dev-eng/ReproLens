"""Tests for Config module."""

from reprolens.config import Config


def test_config_defaults():
    assert Config.MAX_REPAIR_ATTEMPTS == 3
    assert Config.EXECUTION_TIMEOUT_SEC > 0
    assert isinstance(Config.get_fallback_models(), list)


def test_resolve_execution_mode(monkeypatch):
    monkeypatch.setattr(Config, "is_docker_available", lambda: False)
    monkeypatch.setattr(Config, "EXECUTION_MODE", "auto")
    monkeypatch.setattr(Config, "REMOTE_RUNNER_URL", "")
    assert Config.resolve_execution_mode() == "demo"

    monkeypatch.setattr(Config, "is_docker_available", lambda: True)
    assert Config.resolve_execution_mode() == "docker"
