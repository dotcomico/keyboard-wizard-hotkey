"""Global hotkey registration via ``RegisterHotKey``, and parsing of specs like ``"ctrl+alt+w"``."""

from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable

logger = logging.getLogger(__name__)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
#: Suppresses auto-repeat WM_HOTKEYs while the combo is held down.
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

_MODIFIERS: dict[str, int] = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

# Private instance: pystray sets argtypes on the shared ctypes.windll.user32.
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
]
_user32.GetMessageW.restype = wintypes.BOOL
_user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
]
_user32.PeekMessageW.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]
_user32.PostThreadMessageW.restype = wintypes.BOOL


def _parse_key(name: str) -> int | None:
    """Return the VK code for A-Z, 0-9 or F1-F24, else None."""
    # Letter and digit VKs equal their uppercase ASCII codes; F1 is 0x70.
    if len(name) == 1 and ("a" <= name <= "z" or "0" <= name <= "9"):
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit():
        number = int(name[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1
    return None


def parse_hotkey(spec: str) -> tuple[int, int]:
    """Parse a spec like ``"ctrl+alt+w"`` into ``(modifiers, vk)``.

    Case- and whitespace-insensitive; requires at least one modifier and
    exactly one key. ``MOD_NOREPEAT`` is added by the listener, not here.

    Raises:
        ValueError: If the spec is malformed.
    """
    parts = [part.strip().lower() for part in spec.split("+")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"Invalid hotkey: {spec!r}")

    mods = 0
    vk: int | None = None
    for part in parts:
        if part in _MODIFIERS:
            mods |= _MODIFIERS[part]
            continue
        key = _parse_key(part)
        if key is None:
            raise ValueError(f"Unknown key {part!r} in hotkey {spec!r}")
        if vk is not None:
            raise ValueError(f"Hotkey {spec!r} has more than one key")
        vk = key

    if mods == 0:
        raise ValueError(f"Hotkey {spec!r} needs at least one modifier")
    if vk is None:
        raise ValueError(f"Hotkey {spec!r} has no key")
    return mods, vk


_MODIFIER_LABELS = ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift"), (MOD_WIN, "Win"))


def format_hotkey(spec: str) -> str:
    """Return ``spec`` for display, e.g. ``"alt + CTRL+w"`` → ``"Ctrl+Alt+W"``.

    Raises:
        ValueError: If the spec is malformed.
    """
    mods, vk = parse_hotkey(spec)
    labels = [label for flag, label in _MODIFIER_LABELS if mods & flag]
    labels.append(f"F{vk - 0x70 + 1}" if vk >= 0x70 else chr(vk))
    return "+".join(labels)


class HotkeyUnavailable(Exception):
    """Raised when ``RegisterHotKey`` fails, usually because another app owns the combo."""


class HotkeyListener:
    """Owns one system-wide hotkey on a dedicated message-loop thread.

    ``RegisterHotKey`` is used instead of a keyboard hook: letter VK codes are
    layout-independent, so the hotkey also fires under Hebrew; the OS consumes
    the combo; no other keystroke is ever observed; and a taken combo fails
    loudly with error 1409. ``WM_HOTKEY`` goes to the registering thread's
    queue, so registration, the message loop and unregistration share one
    thread.
    """

    _HOTKEY_ID = 1

    def __init__(self, mods: int, vk: int, callback: Callable[[], None]) -> None:
        self._mods = mods
        self._vk = vk
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._registered = threading.Event()
        self._error: int | None = None

    def start(self) -> None:
        """Register the hotkey and start listening; blocks until registration completes.

        Raises:
            HotkeyUnavailable: If registration fails or times out.
        """
        self._registered.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="kbwizard-hotkey", daemon=True)
        self._thread.start()
        # Safety net: a hung registration must not freeze the app at launch.
        if not self._registered.wait(timeout=5.0):
            self._error = -1
        if self._error is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
            hint = (
                " (already registered by another app)"
                if self._error == ERROR_HOTKEY_ALREADY_REGISTERED
                else ""
            )
            raise HotkeyUnavailable(f"RegisterHotKey failed: error {self._error}{hint}")

    def stop(self) -> None:
        """Stop the message loop, which unregisters the hotkey; safe to call more than once."""
        if self._thread is None:
            return
        if self._thread_id is not None:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None

    def _run(self) -> None:
        msg = wintypes.MSG()
        # Create this thread's message queue before stop() can post WM_QUIT to it.
        _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)
        self._thread_id = threading.get_native_id()

        if not _user32.RegisterHotKey(None, self._HOTKEY_ID, self._mods | MOD_NOREPEAT, self._vk):
            self._error = ctypes.get_last_error()
            self._registered.set()
            return
        self._registered.set()

        try:
            # GetMessageW returns 0 on WM_QUIT and -1 on error.
            while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                    try:
                        self._callback()
                    except Exception:
                        # Never let one bad press kill the listener.
                        logger.exception("Hotkey callback failed")
        finally:
            _user32.UnregisterHotKey(None, self._HOTKEY_ID)

