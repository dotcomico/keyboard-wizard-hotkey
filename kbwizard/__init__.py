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
