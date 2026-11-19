"""Tracks when the clipboard last changed, to detect a terminal's copy-on-select.

Terminals with copy-on-select put the selection on the clipboard before
the hotkey is pressed, so a later Ctrl+C finds nothing to copy. A
background thread polls the clipboard sequence number, and a change made
by another process just before the press is treated as the selection.
Every clipboard write the app makes is reported via ``mark_known_sequence``
so it is never mistaken for such a change.
"""

from __future__ import annotations

import threading
import time

import win32clipboard

#: Sequence-number poll interval; one cheap call, no clipboard open/close.
_WATCH_POLL_INTERVAL_SECONDS = 0.2

#: A change this recent at hotkey time counts as the user's selection.
_RECENT_CHANGE_WINDOW_SECONDS = 1.5

#: A watcher that hasn't polled for this long is stopped or starved, so
#: its baseline is not trusted and capture falls back to Ctrl+C.
_WATCH_STALE_AFTER_SECONDS = _WATCH_POLL_INTERVAL_SECONDS * 3

_watch_thread: threading.Thread | None = None
_watch_stop_event: threading.Event | None = None
_watch_lock = threading.Lock()
_last_seen_sequence: int | None = None
_last_seen_timestamp: float | None = None
_last_poll_timestamp: float | None = None


def start_watching() -> None:
    """Start the background watcher; a no-op if it is already running."""
    global _watch_thread, _watch_stop_event
    if _watch_thread is not None:
        return
    _watch_stop_event = threading.Event()
    stop_event = _watch_stop_event

    # Prime the baseline before returning, so content already on the
    # clipboard is never treated as a fresh change.
    mark_known_sequence(win32clipboard.GetClipboardSequenceNumber())

    def _loop() -> None:
        global _last_seen_sequence, _last_seen_timestamp, _last_poll_timestamp
        while not stop_event.is_set():
            if stop_event.wait(_WATCH_POLL_INTERVAL_SECONDS):
                break
            sequence = win32clipboard.GetClipboardSequenceNumber()
            with _watch_lock:
                # Recorded on every poll so a live watcher can be told
                # apart from a stopped one.
                _last_poll_timestamp = time.monotonic()
                if sequence != _last_seen_sequence:
                    _last_seen_sequence = sequence
                    _last_seen_timestamp = time.monotonic()

    _watch_thread = threading.Thread(
        target=_loop, name="clipboard-watcher", daemon=True
    )
    _watch_thread.start()


def stop_watching() -> None:
    """Stop the watcher; safe to call if it was never started."""
    global _watch_thread, _watch_stop_event
    if _watch_stop_event is not None:
        _watch_stop_event.set()
    if _watch_thread is not None:
        _watch_thread.join(timeout=_WATCH_POLL_INTERVAL_SECONDS * 2)
    _watch_thread = None
    _watch_stop_event = None
    _forget_watch_state()


def _forget_watch_state() -> None:
    """Clear the baseline so a stopped watcher's last reading is not trusted."""
    global _last_seen_sequence, _last_seen_timestamp, _last_poll_timestamp
    with _watch_lock:
        _last_seen_sequence = None
        _last_seen_timestamp = None
        _last_poll_timestamp = None


def mark_known_sequence(sequence: int) -> None:
    """Record ``sequence`` as caused by the app rather than by another process.

    Called for every clipboard write the app makes, and at startup to prime
    the baseline.
    """
    global _last_seen_sequence, _last_seen_timestamp, _last_poll_timestamp
    with _watch_lock:
        _last_seen_sequence = sequence
        _last_seen_timestamp = None
        _last_poll_timestamp = time.monotonic()


def changed_recently(sequence: int) -> bool:
    """Return True if another process wrote ``sequence`` to the clipboard just now.

    A sequence the watcher has recorded must be within
    ``_RECENT_CHANGE_WINDOW_SECONDS``. One it has not recorded yet is recent by
    construction, since the watcher is at most one poll behind; requiring it
    to be recorded would leave a blind spot one poll wide.
    """
    with _watch_lock:
        if _last_seen_sequence is None:
            return False  # watcher never started, or has been stopped
        now = time.monotonic()
        if (
            _last_poll_timestamp is None
            or (now - _last_poll_timestamp) > _WATCH_STALE_AFTER_SECONDS
        ):
            # Starved or dead watcher: its baseline may be arbitrarily old.
            return False
        if sequence != _last_seen_sequence:
            return True
        return (
            _last_seen_timestamp is not None
            and (now - _last_seen_timestamp) <= _RECENT_CHANGE_WINDOW_SECONDS
        )
