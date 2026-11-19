"""Switches the foreground window's input language after a conversion.

Only installed layouts are used: ``LoadKeyboardLayout`` is never called,
because it silently adds a layout to the user's language list. Input
language is per-thread, so the switch is requested by posting
``WM_INPUTLANGCHANGEREQUEST`` to the target window.
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from enum import Enum

from kbwizard.core.layouts import LANGIDS
from kbwizard.win32.window import foreground_window

logger = logging.getLogger(__name__)


class SwitchResult(Enum):
    """Outcome of ``switch_foreground_to``."""
    SWITCHED = "switched"
    ALREADY = "already"
    NOT_INSTALLED = "not_installed"
    NO_WINDOW = "no_window"


WM_INPUTLANGCHANGEREQUEST = 0x0050

#: ctypes may return a pointer-sized HKL as negative; masking keeps it
#: a non-negative int so comparisons are consistent.
_PTR_MASK = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1

# Private instance: pystray sets argtypes on the shared ctypes.windll.user32.
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD

# HKL is pointer-sized, hence c_void_p.
_user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
_user32.GetKeyboardLayout.restype = ctypes.c_void_p

_user32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
_user32.GetKeyboardLayoutList.restype = ctypes.c_int

# lParam as c_void_p so an HKL with the high bit set doesn't overflow.
_user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, ctypes.c_void_p]
_user32.PostMessageW.restype = wintypes.BOOL


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


_user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
_user32.GetGUIThreadInfo.restype = wintypes.BOOL


def _langid(hkl: int) -> int:
    """Return an HKL's LANGID (low word; the high word is the device handle)."""
    return hkl & 0xFFFF


def pick_layout(hkls: list[int], lang: str) -> int | None:
    """Return the HKL for ``lang``: exact LANGID first, then same primary language, else None."""
    wanted = LANGIDS.get(lang)
    if wanted is None:
        return None
    for hkl in hkls:
        if _langid(hkl) == wanted:
            return hkl
    primary = wanted & 0x3FF
    for hkl in hkls:
        if _langid(hkl) & 0x3FF == primary:
            return hkl
    return None


def _hkl_to_int(value: int | None) -> int:
    return (value or 0) & _PTR_MASK


def installed_layouts() -> list[int]:
    """Return every HKL in the user's input-language list as a non-negative int."""
    count = _user32.GetKeyboardLayoutList(0, None)
    if count <= 0:
        return []
    buffer = (ctypes.c_void_p * count)()
    got = _user32.GetKeyboardLayoutList(count, buffer)
    return [_hkl_to_int(buffer[i]) for i in range(max(got, 0))]


def _window_thread(hwnd: int) -> int:
    return _user32.GetWindowThreadProcessId(hwnd, None)


def _thread_layout(tid: int) -> int:
    return _hkl_to_int(_user32.GetKeyboardLayout(tid))


def _focus_window(tid: int) -> int:
    """Return the thread's focused control, or 0 if none."""
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not _user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return 0
    return info.hwndFocus or 0


def _post(hwnd: int, hkl: int) -> bool:
    return bool(_user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl))


def switch_foreground_to(lang: str) -> SwitchResult:
    """Ask the foreground window to switch its input language to ``lang``.

    The request is posted, so ``SWITCHED`` means it was sent, not yet applied.
    """
    hwnd = foreground_window()
    if not hwnd:
        return SwitchResult.NO_WINDOW

    tid = _window_thread(hwnd)
    target = pick_layout(installed_layouts(), lang)
    if target is None:
        return SwitchResult.NOT_INSTALLED

    current = _thread_layout(tid)
    if _langid(current) == _langid(target):
        return SwitchResult.ALREADY

    # Some apps (dialogs, embedded edit controls) only honor the request
    # from the focused control.
    focus = _focus_window(tid)
    if focus:
        _post(focus, target)
    if focus != hwnd:
        _post(hwnd, target)
    logger.info("Requested input language %s (LANGID 0x%04X)", lang, _langid(target))
    return SwitchResult.SWITCHED
