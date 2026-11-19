"""Unit tests for winput's struct layout, chords and wait/release helpers; nothing is injected."""

from __future__ import annotations

import ctypes

import pytest

from kbwizard.win32 import winput


def test_input_struct_has_the_size_sendinput_expects():
    """SendInput rejects the call outright if cbSize != sizeof(INPUT)."""
    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(winput.INPUT) == expected


def _summary(events):
    return [
        (e.type, e.ki.wVk, bool(e.ki.dwFlags & winput.KEYEVENTF_KEYUP))
        for e in events
    ]


def test_chord_is_mod_down_key_down_key_up_mod_up():
    events = winput._chord_events(winput.VK_CONTROL, winput.VK_C)
    assert _summary(events) == [
        (winput.INPUT_KEYBOARD, winput.VK_CONTROL, False),
        (winput.INPUT_KEYBOARD, winput.VK_C, False),
        (winput.INPUT_KEYBOARD, winput.VK_C, True),
        (winput.INPUT_KEYBOARD, winput.VK_CONTROL, True),
    ]


def test_chord_fills_scan_codes():
    events = winput._chord_events(winput.VK_CONTROL, winput.VK_V)
    assert all(e.ki.wScan != 0 for e in events)


@pytest.fixture
def sent(monkeypatch):
    """Capture what would have been injected instead of injecting it."""
    batches: list[list] = []
    monkeypatch.setattr(winput, "_send", lambda events: batches.append(_summary(events)))
    return batches


def test_send_copy_and_paste_use_ctrl_c_and_ctrl_v(sent):
    winput.send_copy()
    winput.send_paste()
    assert [batch[1][1] for batch in sent] == [winput.VK_C, winput.VK_V]
    assert all(batch[0][1] == winput.VK_CONTROL for batch in sent)


def _fake_keys_down(monkeypatch, down: set[int]) -> None:
    monkeypatch.setattr(winput, "_is_key_down", lambda vk: vk in down)


def test_keys_still_down_reports_only_held_keys(monkeypatch):
    _fake_keys_down(monkeypatch, {winput.VK_MENU})
    assert winput.keys_still_down(winput.HOTKEY_MODIFIER_VKS) == [winput.VK_MENU]


def test_wait_returns_true_when_keys_are_already_up(monkeypatch):
    _fake_keys_down(monkeypatch, set())
    assert winput.wait_for_keys_released(winput.HOTKEY_MODIFIER_VKS, timeout=0.05)


def test_wait_returns_true_once_keys_are_released(monkeypatch):
    down = {winput.VK_CONTROL}
    polls = {"n": 0}

    def fake(vk):
        polls["n"] += 1
        if polls["n"] > 3:
            down.clear()
        return vk in down

    monkeypatch.setattr(winput, "_is_key_down", fake)
    assert winput.wait_for_keys_released([winput.VK_CONTROL], timeout=1.0, poll=0.001)


def test_wait_times_out_while_a_key_stays_down(monkeypatch):
    _fake_keys_down(monkeypatch, {winput.VK_CONTROL})
    assert (
        winput.wait_for_keys_released(
            iter([winput.VK_CONTROL]), timeout=0.02, poll=0.005
        )
        is False
    )


def test_release_keys_sends_ups_only_for_held_keys(monkeypatch, sent):
    _fake_keys_down(monkeypatch, {winput.VK_CONTROL, winput.VK_MENU})
    winput.release_keys(winput.HOTKEY_MODIFIER_VKS)
    assert sent == [
        [
            (winput.INPUT_KEYBOARD, winput.VK_CONTROL, True),
            (winput.INPUT_KEYBOARD, winput.VK_MENU, True),
        ]
    ]


def test_send_raises_oserror_when_sendinput_injects_fewer(monkeypatch):
    class FakeUser32:
        def SendInput(self, count, array, size):
            return 0

    monkeypatch.setattr(winput, "_user32", FakeUser32())
    with pytest.raises(OSError):
        winput._send([winput.INPUT(type=winput.INPUT_KEYBOARD)])
