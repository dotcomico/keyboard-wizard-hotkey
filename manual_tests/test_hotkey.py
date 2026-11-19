"""Manual check that the ``RegisterHotKey`` hotkey fires under any keyboard layout.

Run: .venv/Scripts/python.exe manual_tests/test_hotkey.py

1. With English active in any window, press Ctrl+Alt+W.
   Expected: "fired" with LANGID 0x0409.
2. Switch that window to Hebrew and press Ctrl+Alt+W again.
   Expected: "fired" with LANGID 0x040D.
3. Hold Ctrl+Alt+W for a second. Expected: exactly one "fired"
   (MOD_NOREPEAT), and the focused app receives no "w".
4. Start a second copy while this one runs. Expected: "Hotkey
   unavailable ... error 1409".
5. Press Ctrl+C here. Expected: "Stopped.", and the hotkey can be
   registered again.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Non-ASCII output would raise on a cp1252 console.
sys.stdout.reconfigure(encoding="utf-8")

# Make the project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kbwizard.win32 import layout_switch, window  # noqa: E402
from kbwizard.app.config import DEFAULT_HOTKEY  # noqa: E402
from kbwizard.win32.hotkey import HotkeyListener, HotkeyUnavailable, parse_hotkey  # noqa: E402


def _on_fired() -> None:
    hwnd = window.foreground_window()
    langid = layout_switch._thread_layout(layout_switch._window_thread(hwnd)) & 0xFFFF if hwnd else 0
    print(f"[{time.strftime('%H:%M:%S')}] fired -- foreground layout LANGID 0x{langid:04X}", flush=True)


def main() -> None:
    print("=== Keyboard Wizard hotkey.py manual test ===\n")
    mods, vk = parse_hotkey(DEFAULT_HOTKEY)
    listener = HotkeyListener(mods, vk, _on_fired)
    try:
        listener.start()
    except HotkeyUnavailable as exc:
        print(f"Hotkey unavailable: {exc}")
        return

    print(f"Listening for {DEFAULT_HOTKEY}. Press Ctrl+C here to exit.\n")
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        print("Stopped.")


if __name__ == "__main__":
    main()
