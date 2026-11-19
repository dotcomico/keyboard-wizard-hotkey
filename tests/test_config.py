"""Unit tests for Config: first-run defaults, backfill, unknown keys and corrupt files."""

from __future__ import annotations

import json

import pytest

from kbwizard.app.config import DEFAULT_HOTKEY, Config


@pytest.fixture
def cfg_path(tmp_path, monkeypatch):
    path = tmp_path / "KeyboardWizard" / "config.json"
    monkeypatch.setattr(Config, "config_path", staticmethod(lambda: path))
    return path


def test_first_run_writes_defaults(cfg_path):
    config = Config.load()
    assert config.hotkey == DEFAULT_HOTKEY
    assert config.switch_layout_after_convert is True
    assert config.keep_result_on_clipboard is False
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["hotkey"] == DEFAULT_HOTKEY


def test_missing_keys_backfilled_and_unknown_dropped(cfg_path):
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(json.dumps({"run_at_startup": True, "bogus": 1}), encoding="utf-8")
    config = Config.load()
    assert config.run_at_startup is True
    assert config.hotkey == DEFAULT_HOTKEY
    assert not hasattr(config, "bogus")


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_corrupt_file_resets_to_defaults(cfg_path, content):
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(content, encoding="utf-8")
    config = Config.load()
    assert config == Config()
    assert json.loads(cfg_path.read_text(encoding="utf-8")) == json.loads(
        json.dumps(Config().__dict__)
    )


def test_save_roundtrip(cfg_path):
    config = Config.load()
    config.switch_layout_after_convert = False
    config.save()
    assert Config.load().switch_layout_after_convert is False
