"""Manual check of clipboard capture and replace in a real app.

Run: .venv/Scripts/python.exe manual_tests/test_clipboard_io.py

1. Copy something recognizable (e.g. ``ORIGINAL``) before starting.
2. Within the 3-second countdown, select a word or two in an editable
   field (Notepad, a browser textarea, VS Code), then leave the keyboard.
3. Expected: "Captured N character(s)" with N matching the selection.
   "No text captured" means nothing was selected or the window is
   elevated (SendInput can't reach admin windows).
4. Expected: the selection is replaced by its reverse (``hello`` ->
   ``olleh``), not by the old clipboard. Seeing the old clipboard means
   the paste-settle delay is too short for that app.
5. Expected final line: "Clipboard restored: YES".
6. Press Win+V. Expected: no entry for the reversed text or the restore
   (the app's own Ctrl+C entry may appear; known limitation).

Only lengths are printed, never the text.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Make the project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kbwizard.win32 import clipboard_io, clipboard_watcher  # noqa: E402

COUNTDOWN_SECONDS = 3


def _describe(text: str | None) -> str:
    return "empty / non-text" if text is None else f"{len(text)} character(s)"


def main() -> None:
    print("=== KeyboardWizard clipboard_io manual test ===\n")

    clipboard_watcher.start_watching()
    try:
        before = clipboard_io._read_clipboard_text()
        print(f"Clipboard BEFORE test: {_describe(before)}\n")

        print(f"Select some text in an editable field within {COUNTDOWN_SECONDS} seconds...")
        for remaining in range(COUNTDOWN_SECONDS, 0, -1):
            print(f"  {remaining}...")
            time.sleep(1)

        print("\nCapturing now (injecting Ctrl+C)...")
        captured = clipboard_io.capture_selected_text()
        if captured is None:
            print("  -> No text captured. Nothing to replace; stopping.")
            return
        print(f"  -> Captured {len(captured)} character(s).")

        print("\nReplacing selection with its reverse (injecting Ctrl+V)...")
        clipboard_io.replace_selection(captured[::-1])
        print("  -> Done. Check the target window shows the reversed text.")
    finally:
        clipboard_watcher.stop_watching()

    after = clipboard_io._read_clipboard_text()
    print(f"\nClipboard AFTER test: {_describe(after)}")
    print(f"Clipboard restored: {'YES' if after == before else 'NO'}")
    if after != before:
        print("  (Expected only if you had non-text data, e.g. an image, on the")
        print("   clipboard -- only text is preserved.)")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
