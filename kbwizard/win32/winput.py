"""Synthetic keyboard input via ``SendInput``: Ctrl+C, Ctrl+V and releasing held keys.

Plain ctypes is used instead of ``keyboard`` or ``pynput`` because both
install a global keyboard hook; the app has none, so it cannot log
keystrokes. Injected input merges with the physical keyboard state, so
callers wait for the hotkey to be released, and force key-ups on timeout,
before injecting Ctrl+C.
"""

from __future__ import annotations

import ctypes
import time
from collections.abc import Iterable
from ctypes import wintypes

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
MAPVK_VK_TO_VSC = 0

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_C = 0x43
VK_V = 0x56

#: Every modifier a hotkey could use; all must be up before injecting.
HOTKEY_MODIFIER_VKS = (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)

#: ``GetAsyncKeyState`` sets the high bit while the key is physically down.
_KEY_DOWN_MASK = 0x8000

# ctypes has no ULONG_PTR; WPARAM is the same pointer-sized type.
ULONG_PTR = wintypes.WPARAM


# SendInput rejects a cbSize other than sizeof(INPUT), which is sized by the
# largest union member (40 bytes on x64). The full union is therefore
# declared even though only KEYBDINPUT is used.
class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _INPUTUNION(ctypes.Union):
    _fields_ = (
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = (
        ("type", wintypes.DWORD),
        ("u", _INPUTUNION),
    )


# Private instance: pystray sets argtypes on the shared ctypes.windll.user32.

_user32 = ctypes.WinDLL("user32", use_last_error=True)

_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT

_user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
_user32.MapVirtualKeyW.restype = wintypes.UINT

_user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
_user32.GetAsyncKeyState.restype = ctypes.c_short


def _key_event(vk: int, *, key_up: bool) -> INPUT:
    """Build one keyboard ``INPUT`` for ``vk``.

    The scan code is set as well, because some apps (games, remote desktop
    clients) read ``wScan`` and ignore ``wVk``.
    """
    event = INPUT(type=INPUT_KEYBOARD)
    event.ki = KEYBDINPUT(
        wVk=vk,
        wScan=_user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC),
        dwFlags=KEYEVENTF_KEYUP if key_up else 0,
        time=0,
        dwExtraInfo=0,
    )
    return event


def _chord_events(mod_vk: int, key_vk: int) -> list[INPUT]:
    """Build modifier-down, key-down, key-up, modifier-up events."""
    return [
        _key_event(mod_vk, key_up=False),
        _key_event(key_vk, key_up=False),
        _key_event(key_vk, key_up=True),
        _key_event(mod_vk, key_up=True),
    ]


def _send(events: list[INPUT]) -> None:
    """Inject ``events`` in one call, which ``SendInput`` keeps from interleaving with other input.

    Raises:
        OSError: If not every event was injected, usually because UIPI
            blocks input to an elevated window.
    """
    if not events:
        return
    array = (INPUT * len(events))(*events)
    sent = _user32.SendInput(len(events), array, ctypes.sizeof(INPUT))
    if sent != len(events):
        error = ctypes.get_last_error()
        raise OSError(error, f"SendInput injected {sent} of {len(events)} events")


def send_copy() -> None:
    """Inject Ctrl+C into the focused window."""
    _send(_chord_events(VK_CONTROL, VK_C))


def send_paste() -> None:
    """Inject Ctrl+V into the focused window."""
    _send(_chord_events(VK_CONTROL, VK_V))


def _is_key_down(vk: int) -> bool:
    return bool(_user32.GetAsyncKeyState(vk) & _KEY_DOWN_MASK)


def keys_still_down(vks: Iterable[int]) -> list[int]:
    """Return the subset of ``vks`` that is currently held, in input order."""
    return [vk for vk in vks if _is_key_down(vk)]


def wait_for_keys_released(
    vks: Iterable[int], timeout: float = 1.0, poll: float = 0.01
) -> bool:
    """Block until none of ``vks`` is held or ``timeout`` seconds pass.

    Returns:
        True once every key is up, False on timeout.
    """
    keys = tuple(vks)  # vks may be a one-shot iterator
    deadline = time.monotonic() + timeout
    while keys_still_down(keys):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll)
    return True


def release_keys(vks: Iterable[int]) -> None:
    """Inject key-ups only for those ``vks`` still held, so no stray key-up is sent."""
    held = keys_still_down(vks)
    _send([_key_event(vk, key_up=True) for vk in held])

