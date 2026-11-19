"""Unit tests for hotkey parsing, plus smoke tests that register a real, unlikely combo."""

from __future__ import annotations

import os

import pytest

from kbwizard.win32 import hotkey

# CI runners have no interactive desktop to own a system-wide hotkey.
needs_desktop = pytest.mark.skipif(
    bool(os.environ.get("CI")), reason="needs an interactive desktop session"
)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("ctrl+alt+w", (hotkey.MOD_CONTROL | hotkey.MOD_ALT, 0x57)),
        (" Ctrl + ALT + W ", (hotkey.MOD_CONTROL | hotkey.MOD_ALT, 0x57)),
        ("control+shift+a", (hotkey.MOD_CONTROL | hotkey.MOD_SHIFT, 0x41)),
        ("win+5", (hotkey.MOD_WIN, 0x35)),
        ("alt+f1", (hotkey.MOD_ALT, 0x70)),
        ("ctrl+alt+shift+F24", (hotkey.MOD_CONTROL | hotkey.MOD_ALT | hotkey.MOD_SHIFT, 0x87)),
        ("w+ctrl", (hotkey.MOD_CONTROL, 0x57)),
    ],
)
def test_parse_hotkey_valid(spec, expected):
    assert hotkey.parse_hotkey(spec) == expected


def test_parse_hotkey_excludes_norepeat():
    mods, _ = hotkey.parse_hotkey("ctrl+alt+w")
    assert not mods & hotkey.MOD_NOREPEAT


@pytest.mark.parametrize(
    "spec",
    ["", "w", "ctrl", "ctrl+alt", "ctrl+w+q", "ctrl+f25", "ctrl+f0", "ctrl+space", "ctrl++w", "ctrl+ab"],
)
def test_parse_hotkey_invalid(spec):
    with pytest.raises(ValueError):
        hotkey.parse_hotkey(spec)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("ctrl+alt+w", "Ctrl+Alt+W"),
        (" w + ALT + control ", "Ctrl+Alt+W"),
        ("win+shift+5", "Shift+Win+5"),
        ("alt+f1", "Alt+F1"),
        ("ctrl+alt+shift+f24", "Ctrl+Alt+Shift+F24"),
    ],
)
def test_format_hotkey(spec, expected):
    assert hotkey.format_hotkey(spec) == expected


def test_format_hotkey_rejects_malformed_spec():
    with pytest.raises(ValueError):
        hotkey.format_hotkey("ctrl+alt+banana")


@needs_desktop
def test_listener_registers_and_stops_unlikely_combo():
    mods, vk = hotkey.parse_hotkey("ctrl+alt+shift+f24")
    listener = hotkey.HotkeyListener(mods, vk, lambda: None)
    try:
        listener.start()
    except hotkey.HotkeyUnavailable:
        pytest.skip("ctrl+alt+shift+F24 already registered")
    thread = listener._thread
    listener.stop()
    assert thread is not None and not thread.is_alive()
    # Unregistered on exit, so it can be registered again.
    again = hotkey.HotkeyListener(mods, vk, lambda: None)
    again.start()
    again.stop()


@needs_desktop
def test_listener_reports_conflict():
    mods, vk = hotkey.parse_hotkey("ctrl+alt+shift+f23")
    first = hotkey.HotkeyListener(mods, vk, lambda: None)
    try:
        first.start()
    except hotkey.HotkeyUnavailable:
        pytest.skip("ctrl+alt+shift+F23 already registered")
    try:
        # A second registration of a held combo fails with 1409.
        with pytest.raises(hotkey.HotkeyUnavailable, match="1409"):
            hotkey.HotkeyListener(mods, vk, lambda: None).start()
    finally:
        first.stop()

