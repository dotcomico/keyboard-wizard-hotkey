"""Unit tests for the first-launch Run-at-startup default."""

from __future__ import annotations

import sys

import pytest

from kbwizard import main
from kbwizard.app.config import Config


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "KeyboardWizard" / "config.json"
    monkeypatch.setattr(Config, "config_path", staticmethod(lambda: path))
    return Config.load()


@pytest.fixture
def enable_calls(monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(main.startup, "enable", lambda: calls.append(True))
    return calls


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)


def test_first_exe_launch_enables_startup(config, enable_calls, frozen):
    main._enable_startup_on_first_run(config)
    assert enable_calls == [True]
    assert Config.load().startup_default_applied is True


def test_default_applied_only_once(config, enable_calls, frozen):
    main._enable_startup_on_first_run(config)
    main._enable_startup_on_first_run(Config.load())
    assert enable_calls == [True]


def test_source_run_never_registers(config, enable_calls, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    main._enable_startup_on_first_run(config)
    assert enable_calls == []
    assert config.startup_default_applied is False


def test_registry_error_is_logged_not_raised(config, frozen, monkeypatch):
    def fail() -> None:
        raise OSError("policy-locked Run key")

    monkeypatch.setattr(main.startup, "enable", fail)
    main._enable_startup_on_first_run(config)
    assert config.startup_default_applied is True
