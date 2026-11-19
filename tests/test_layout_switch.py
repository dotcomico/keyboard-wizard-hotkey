"""Unit tests for layout_switch: the layout picker and the switch logic over faked Win32 calls."""

from __future__ import annotations

import pytest

from kbwizard.win32 import layout_switch
from kbwizard.win32.layout_switch import SwitchResult, pick_layout

HE = 0x040D040D
EN_US = 0x04090409
EN_GB = 0x08090809
HE_DEVICE = 0xF03D040D  # high word is a device handle; low word still he
RU = 0x04190419


def test_exact_langid_preferred_over_primary_fallback():
    assert pick_layout([EN_GB, HE, EN_US], "en") == EN_US


def test_primary_language_fallback():
    assert pick_layout([HE, EN_GB], "en") == EN_GB


def test_none_when_language_missing():
    assert pick_layout([EN_US, RU], "he") is None
    assert pick_layout([], "en") is None


def test_unknown_language_code():
    assert pick_layout([EN_US, HE], "ru") is None


def test_device_handle_in_high_word_still_matches():
    assert pick_layout([EN_US, HE_DEVICE], "he") == HE_DEVICE


def test_64bit_high_bit_hkl_matches():
    hkl = 0xFFFFFFFFF03D040D
    assert pick_layout([hkl], "he") == hkl


def test_installed_layouts_returns_non_negative_ints():
    layouts = layout_switch.installed_layouts()
    assert layouts, "every Windows session has at least one input layout"
    assert all(isinstance(h, int) and h > 0 for h in layouts)


@pytest.fixture
def win(monkeypatch):
    """Fake the Win32 wrappers; return knobs plus a list of posted messages."""

    class Knobs:
        foreground = 0x100
        focus = 0x200
        current = EN_US
        installed = [EN_US, HE]
        posts: list[tuple[int, int]] = []

    knobs = Knobs()
    knobs.posts = []
    monkeypatch.setattr(layout_switch, "foreground_window", lambda: knobs.foreground)
    monkeypatch.setattr(layout_switch, "_window_thread", lambda hwnd: 42)
    monkeypatch.setattr(layout_switch, "_thread_layout", lambda tid: knobs.current)
    monkeypatch.setattr(layout_switch, "installed_layouts", lambda: knobs.installed)
    monkeypatch.setattr(layout_switch, "_focus_window", lambda tid: knobs.focus)
    monkeypatch.setattr(
        layout_switch, "_post", lambda hwnd, hkl: knobs.posts.append((hwnd, hkl)) or True
    )
    return knobs


def test_no_window(win):
    win.foreground = 0
    assert layout_switch.switch_foreground_to("he") is SwitchResult.NO_WINDOW
    assert win.posts == []


def test_not_installed(win):
    win.installed = [EN_US]
    assert layout_switch.switch_foreground_to("he") is SwitchResult.NOT_INSTALLED
    assert win.posts == []


def test_already_active(win):
    win.current = HE_DEVICE  # same LANGID, different device handle
    assert layout_switch.switch_foreground_to("he") is SwitchResult.ALREADY
    assert win.posts == []


def test_switched_posts_to_focus_and_foreground(win):
    assert layout_switch.switch_foreground_to("he") is SwitchResult.SWITCHED
    assert win.posts == [(0x200, HE), (0x100, HE)]


def test_switched_posts_once_when_focus_is_foreground(win):
    win.focus = 0x100
    assert layout_switch.switch_foreground_to("he") is SwitchResult.SWITCHED
    assert win.posts == [(0x100, HE)]


def test_switched_without_focus_posts_to_foreground(win):
    win.focus = 0
    assert layout_switch.switch_foreground_to("he") is SwitchResult.SWITCHED
    assert win.posts == [(0x100, HE)]


def test_never_loads_keyboard_layout():
    # Loading a layout would add it to the user's language list.
    import inspect

    assert "_user32.LoadKeyboardLayout" not in inspect.getsource(layout_switch)
