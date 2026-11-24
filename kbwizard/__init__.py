"""Keyboard Wizard: retype text that was typed in the wrong keyboard layout.

Subpackages, with dependencies pointing downward only: ``app`` (pipeline,
settings, tray), ``win32`` (thin Win32 adapters) and ``core`` (pure
conversion logic). ``main`` is the entry point.
"""

__version__ = "1.0.0"

#: Names the %APPDATA% folder, Run-key value, tray icon and mutex.
#: Changing it orphans existing settings and startup entries.
APP_NAME = "KeyboardWizard"

APP_DISPLAY_NAME = "Keyboard Wizard"

#: Shown in the exe's file properties and the tray's About entry.
APP_AUTHOR = "Dotan Siman Tov"
APP_COPYRIGHT = f"Copyright (c) 2026 {APP_AUTHOR}. All rights reserved."
