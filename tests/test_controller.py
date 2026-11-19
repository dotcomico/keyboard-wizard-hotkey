"""Unit tests for HotkeyController with every collaborator faked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kbwizard.app import controller
from kbwizard.app.config import DEFAULT_HOTKEY, Config
from kbwizard.app.state import State
from kbwizard.app.status import Status
from kbwizard.win32 import hotkey
from kbwizard.win32.layout_switch import SwitchResult

HWND = 0x1234


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return record

    def named(self, name):
        return [c for c in self.calls if c[0] == name]


@pytest.fixture
def env(monkeypatch):
    """Fake every collaborator; return a namespace of knobs and recorded calls."""
    rec = Recorder()
    knobs = SimpleNamespace(
        text="akuo",
        direction=("en", "he"),
        result="שלום",
        released=True,
        still_down=[0x12],
        foreground=[HWND],  # successive foreground_window() values
        switch_result=SwitchResult.SWITCHED,
        capture_error=None,
        rec=rec,
        statuses=[],
    )

    def capture():
        if knobs.capture_error:
            raise knobs.capture_error
        return knobs.text

    monkeypatch.setattr(
        controller,
        "clipboard_io",
        SimpleNamespace(
            capture_selected_text=capture,
            replace_selection=rec("replace"),
        ),
    )
    monkeypatch.setattr(
        controller,
        "clipboard_watcher",
        SimpleNamespace(
            start_watching=rec("start_watching"),
            stop_watching=rec("stop_watching"),
        ),
    )
    monkeypatch.setattr(
        controller,
        "converter",
        SimpleNamespace(
            detect_direction=lambda text: knobs.direction,
            convert=lambda text, src, tgt: knobs.result,
        ),
    )

    def wait(vks, timeout=1.0):
        rec("wait")(vks, timeout)
        return knobs.released

    monkeypatch.setattr(
        controller,
        "winput",
        SimpleNamespace(
            HOTKEY_MODIFIER_VKS=(0x11, 0x12, 0x10, 0x5B, 0x5C),
            wait_for_keys_released=wait,
            keys_still_down=lambda vks: knobs.still_down,
            release_keys=rec("release"),
        ),
    )

    def switch(lang):
        rec("switch")(lang)
        return knobs.switch_result

    monkeypatch.setattr(
        controller,
        "layout_switch",
        SimpleNamespace(switch_foreground_to=switch, SwitchResult=SwitchResult),
    )

    def foreground():
        return knobs.foreground.pop(0) if len(knobs.foreground) > 1 else knobs.foreground[0]

    monkeypatch.setattr(controller, "window", SimpleNamespace(foreground_window=foreground))
    return knobs


def make_controller(env, **config_overrides) -> controller.HotkeyController:
    ctl = controller.HotkeyController(Config(**config_overrides), on_status=env.statuses.append)
    ctl._vk = 0x57
    return ctl


def test_success_converts_pastes_and_switches(env):
    ctl = make_controller(env)
    ctl._run_cycle(HWND)

    assert env.statuses == [Status.CONVERTED_TO_HE]
    assert env.rec.named("replace") == [("replace", ("שלום",), {"keep_on_clipboard": False})]
    assert env.rec.named("switch") == [("switch", ("he",), {})]
    assert ctl._state.state is State.IDLE


def test_waits_for_modifiers_and_hotkey_vk(env):
    make_controller(env)._run_cycle(HWND)
    (_, (vks, timeout), _), = env.rec.named("wait")
    assert 0x57 in vks and 0x12 in vks
    assert timeout == 1.0
    assert env.rec.named("release") == []


def test_keys_not_released_forces_release(env):
    env.released = False
    make_controller(env)._run_cycle(HWND)
    assert env.rec.named("release") == [("release", ([0x12],), {})]
    assert env.statuses == [Status.CONVERTED_TO_HE]


@pytest.mark.parametrize("empty", [None, ""])
def test_no_text_selected(env, empty):
    env.text = empty
    make_controller(env)._run_cycle(HWND)
    assert env.statuses == [Status.NO_TEXT_SELECTED]
    assert env.rec.named("replace") == []


def test_unchanged_is_nothing_to_convert(env):
    env.text = env.result = "123"
    make_controller(env)._run_cycle(HWND)
    assert env.statuses == [Status.NOTHING_TO_CONVERT]
    assert env.rec.named("replace") == []


def test_focus_changed_aborts_before_paste(env):
    env.foreground = [0x9999]
    make_controller(env)._run_cycle(HWND)
    assert env.statuses == [Status.FOCUS_CHANGED]
    assert env.rec.named("replace") == []
    assert env.rec.named("switch") == []


def test_exception_reports_failure_and_resets_state(env):
    env.capture_error = RuntimeError("boom")
    ctl = make_controller(env)
    assert ctl._state.try_begin()
    ctl._run_cycle(HWND)
    assert env.statuses == [Status.CONVERT_FAILED]
    assert ctl._state.state is State.IDLE


def test_switch_disabled_skips_switch(env):
    make_controller(env, switch_layout_after_convert=False)._run_cycle(HWND)
    assert env.rec.named("switch") == []
    assert env.statuses == [Status.CONVERTED_TO_HE]


def test_layout_not_installed(env):
    env.switch_result = SwitchResult.NOT_INSTALLED
    make_controller(env)._run_cycle(HWND)
    assert env.statuses == [Status.LAYOUT_NOT_INSTALLED_HE]


@pytest.mark.parametrize("result", [SwitchResult.ALREADY, SwitchResult.NO_WINDOW])
def test_other_switch_results_still_converted(env, result):
    env.switch_result = result
    make_controller(env)._run_cycle(HWND)
    assert env.statuses == [Status.CONVERTED_TO_HE]


def test_hebrew_to_english_direction(env):
    env.text, env.direction, env.result = "שלום", ("he", "en"), "akuo"
    make_controller(env)._run_cycle(HWND)
    assert env.statuses == [Status.CONVERTED_TO_EN]
    assert env.rec.named("switch") == [("switch", ("en",), {})]


def test_keep_result_on_clipboard_passed_through(env):
    make_controller(env, keep_result_on_clipboard=True)._run_cycle(HWND)
    assert env.rec.named("replace")[0][2] == {"keep_on_clipboard": True}


def test_config_read_at_press_time(env):
    ctl = make_controller(env)
    ctl._config.switch_layout_after_convert = False  # tray toggles live
    ctl._run_cycle(HWND)
    assert env.rec.named("switch") == []


def test_never_logs_text(env, caplog):
    caplog.set_level("DEBUG", logger="kbwizard")
    make_controller(env)._run_cycle(HWND)
    assert "akuo" not in caplog.text and "שלום" not in caplog.text
    assert "Converted 4 chars en->he" in caplog.text


def test_on_hotkey_spawns_worker_with_press_time_hwnd(env, monkeypatch):
    spawned = []

    class FakeThread:
        def __init__(self, target, args=(), daemon=None):
            spawned.append((target, args, daemon))

        def start(self):
            pass

    monkeypatch.setattr(controller.threading, "Thread", FakeThread)
    ctl = make_controller(env)
    ctl._on_hotkey()
    assert len(spawned) == 1
    assert spawned[0][1] == (HWND,) and spawned[0][2] is True
    assert ctl._state.state is State.BUSY


def test_on_hotkey_while_busy_does_not_spawn(env, monkeypatch):
    spawned = []
    monkeypatch.setattr(controller.threading, "Thread", lambda *a, **k: spawned.append(1))
    ctl = make_controller(env)
    assert ctl._state.try_begin()
    ctl._on_hotkey()
    assert spawned == []


class FakeListener:
    fail = False
    instances: list["FakeListener"] = []

    def __init__(self, mods, vk, callback):
        self.args = (mods, vk)
        self.stopped = False
        FakeListener.instances.append(self)

    def start(self):
        if FakeListener.fail:
            raise hotkey.HotkeyUnavailable("RegisterHotKey failed: error 1409")

    def stop(self):
        self.stopped = True


@pytest.fixture
def fake_listener(monkeypatch):
    FakeListener.fail = False
    FakeListener.instances = []
    monkeypatch.setattr(controller, "HotkeyListener", FakeListener)
    return FakeListener


def test_start_and_stop(env, fake_listener):
    ctl = controller.HotkeyController(Config(), on_status=env.statuses.append)
    ctl.start()
    assert env.rec.named("start_watching")
    assert fake_listener.instances[0].args == (hotkey.MOD_CONTROL | hotkey.MOD_ALT, 0x57)
    assert env.statuses == [Status.READY]
    ctl.stop()
    assert fake_listener.instances[0].stopped
    assert env.rec.named("stop_watching")


def test_start_with_malformed_hotkey_falls_back_to_default(env, fake_listener):
    ctl = controller.HotkeyController(
        Config(hotkey="ctrl+alt+banana"), on_status=env.statuses.append
    )
    ctl.start()
    assert fake_listener.instances[0].args == (hotkey.MOD_CONTROL | hotkey.MOD_ALT, 0x57)
    assert env.statuses == [Status.READY]


def test_hotkey_property_is_the_configured_spec():
    ctl = controller.HotkeyController(Config(hotkey="alt+shift+k"))
    assert ctl.hotkey == "alt+shift+k"


def test_hotkey_property_falls_back_to_default_when_malformed():
    ctl = controller.HotkeyController(Config(hotkey="ctrl+alt+banana"))
    assert ctl.hotkey == DEFAULT_HOTKEY


def test_start_unavailable_stops_watcher_and_propagates(env, fake_listener):
    fake_listener.fail = True
    ctl = controller.HotkeyController(Config(), on_status=env.statuses.append)
    with pytest.raises(hotkey.HotkeyUnavailable):
        ctl.start()
    assert env.rec.named("stop_watching")
    assert env.statuses == []
