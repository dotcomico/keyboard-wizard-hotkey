"""Reads and replaces the focused app's selection via the clipboard, then restores it.

Every clipboard write the app makes lives in this module and is reported
to ``clipboard_watcher.mark_known_sequence``, so the watcher never mistakes
it for a terminal's copy-on-select. Writes are also kept out of Win+V
history and the cloud clipboard. Only ``CF_UNICODETEXT`` is preserved;
other formats on the user's clipboard are lost. Selection text is never
logged, only its length.
"""

from __future__ import annotations

import logging
import struct
import time

import win32clipboard
import win32con

from kbwizard.win32 import clipboard_watcher, winput

_log = logging.getLogger(__name__)

#: How long to wait for the app to put the copied selection on the
#: clipboard; slow Electron and Chromium apps need the margin.
_COPY_TIMEOUT_SECONDS = 0.5

_POLL_INTERVAL_SECONDS = 0.02

#: How long the pasted text stays on the clipboard after Ctrl+V. SendInput
#: only queues keystrokes, and Electron, Chromium and Word read the
#: clipboard asynchronously; restoring too early pastes the user's old
#: clipboard over the selection.
_PASTE_SETTLE_SECONDS = 0.25

#: Keeps the app's writes out of Win+V history and the cloud clipboard.
#: Clipboard managers check for the first format's presence; Windows
#: reads the DWORD flags.
_HISTORY_EXCLUSION_FORMATS: tuple[tuple[str, bytes], ...] = (
    ("ExcludeClipboardContentFromMonitorProcessing", b""),
    ("CanIncludeInClipboardHistory", struct.pack("<I", 0)),
    ("CanUploadToCloudClipboard", struct.pack("<I", 0)),
)

_registered_format_ids: dict[str, int] = {}


def _read_clipboard_text() -> str | None:
    """Return the clipboard's text, or None if it is empty or not text."""
    try:
        win32clipboard.OpenClipboard()
    except Exception:
        # Locked by another process; transient.
        return None

    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return None
        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return data if data else None
    except Exception:
        # Some producers advertise the format but fail the read.
        return None
    finally:
        win32clipboard.CloseClipboard()


def _format_id(name: str) -> int:
    """Return the registered id for clipboard format ``name``, cached for the session."""
    format_id = _registered_format_ids.get(name)
    if format_id is None:
        format_id = win32clipboard.RegisterClipboardFormat(name)
        _registered_format_ids[name] = format_id
    return format_id


def _set_history_exclusion_formats() -> None:
    """Tag the open clipboard to keep it out of history; best effort, failures are ignored."""
    for name, data in _HISTORY_EXCLUSION_FORMATS:
        try:
            win32clipboard.SetClipboardData(_format_id(name), data)
        except Exception:
            _log.debug("Could not set clipboard format %s", name, exc_info=True)


def _write_clipboard_text(
    text: str | None, *, exclude_from_history: bool = False
) -> None:
    """Replace the clipboard with ``text``, or clear it if ``text`` is None."""
    try:
        win32clipboard.OpenClipboard()
    except Exception:
        return

    try:
        win32clipboard.EmptyClipboard()
        if text is not None:
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            if exclude_from_history:
                _set_history_exclusion_formats()
    except Exception:
        # Best effort; the clipboard is always closed below.
        pass
    finally:
        win32clipboard.CloseClipboard()


def _restore_clipboard(original_text: str | None) -> None:
    """Restore the user's text and mark the write as the app's own, not a copy-on-select."""
    _write_clipboard_text(original_text, exclude_from_history=True)
    clipboard_watcher.mark_known_sequence(win32clipboard.GetClipboardSequenceNumber())


def _wait_for_copied_text(before_sequence: int) -> str | None:
    """Poll for copied text until ``_COPY_TIMEOUT_SECONDS`` elapses.

    The sequence number changes on the app's ``EmptyClipboard()`` before its
    ``SetClipboardData()``, so polling continues past the first change until
    a text read succeeds.
    """
    deadline = time.monotonic() + _COPY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if win32clipboard.GetClipboardSequenceNumber() != before_sequence:
            text = _read_clipboard_text()
            if text is not None:
                return text
        time.sleep(_POLL_INTERVAL_SECONDS)
    return None


def capture_selected_text() -> str | None:
    """Return the focused app's selected text, or None if nothing is selected.

    Injects Ctrl+C and restores the original clipboard afterward. The caller
    must wait for the hotkey modifiers to be released first
    (``winput.wait_for_keys_released``), or the copy arrives as Ctrl+Alt+C.
    """
    original_text = _read_clipboard_text()
    original_sequence = win32clipboard.GetClipboardSequenceNumber()

    if original_text and clipboard_watcher.changed_recently(original_sequence):
        # A terminal's copy-on-select already put the selection on the
        # clipboard, so use it directly; nothing was written, so nothing needs
        # restoring. Mark it consumed so a second press doesn't replay it.
        clipboard_watcher.mark_known_sequence(original_sequence)
        _log.debug("Capture via copy-on-select fast path (%d chars)", len(original_text))
        return original_text

    try:
        winput.send_copy()
        captured_text = _wait_for_copied_text(original_sequence)
    finally:
        _restore_clipboard(original_text)

    return captured_text


def replace_selection(text: str, *, keep_on_clipboard: bool = False) -> None:
    """Paste ``text`` over the focused app's selection, then restore the clipboard.

    In a read-only control the paste does nothing and the clipboard is still
    restored.

    Args:
        text: Text to paste.
        keep_on_clipboard: Leave ``text`` on the clipboard instead of
            restoring the original.

    Raises:
        OSError: If input injection fails; the clipboard is restored first.
    """
    original_text = _read_clipboard_text()
    try:
        _write_clipboard_text(text, exclude_from_history=True)
        clipboard_watcher.mark_known_sequence(win32clipboard.GetClipboardSequenceNumber())
        winput.send_paste()
        # Let the target app read the clipboard; see _PASTE_SETTLE_SECONDS.
        time.sleep(_PASTE_SETTLE_SECONDS)
    finally:
        if keep_on_clipboard:
            # Still the app's own write, not a copy-on-select.
            clipboard_watcher.mark_known_sequence(win32clipboard.GetClipboardSequenceNumber())
        else:
            _restore_clipboard(original_text)
    _log.debug("Replaced selection (%d chars)", len(text))
