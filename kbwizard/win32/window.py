"""Foreground window lookup, shared by the focus guard and layout switching."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

# Private instance: pystray sets argtypes on the shared ctypes.windll.user32.
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = wintypes.HWND


def foreground_window() -> int:
    """Return the foreground window handle, or 0 if there is none."""
    return _user32.GetForegroundWindow() or 0
