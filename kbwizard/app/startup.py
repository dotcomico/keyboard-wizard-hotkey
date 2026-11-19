"""Run-at-startup entry in the per-user Run registry key (no admin rights needed)."""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

from kbwizard import APP_NAME

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = APP_NAME

#: Resolved from this file, not sys.argv[0], which depends on how the app was launched.
_MAIN_SCRIPT = Path(__file__).resolve().parents[1] / "main.py"


def _console_free_interpreter() -> str:
    """Prefer ``pythonw.exe`` so a login launch doesn't open a console window."""
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate) if candidate.exists() else sys.executable


def _launch_cmd() -> str:
    """Return the command stored in the Run key.

    A frozen build's ``sys.executable`` is the app itself; in dev mode the
    interpreter needs the entry script. Both paths are quoted since they may
    contain spaces.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{_console_free_interpreter()}" "{_MAIN_SCRIPT}"'


def is_enabled() -> bool:
    """Return whether the startup entry exists; any registry error reads as disabled."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as k:
            winreg.QueryValueEx(k, _RUN_VALUE_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def enable() -> None:
    """Create or update the startup entry."""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_KEY, access=winreg.KEY_SET_VALUE
    ) as k:
        winreg.SetValueEx(k, _RUN_VALUE_NAME, 0, winreg.REG_SZ, _launch_cmd())


def disable() -> None:
    """Remove the startup entry; a missing entry is not an error."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, access=winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, _RUN_VALUE_NAME)
    except (FileNotFoundError, OSError):
        pass
