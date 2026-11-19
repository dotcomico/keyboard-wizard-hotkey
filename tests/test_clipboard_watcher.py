"""Unit tests for clipboard_watcher.changed_recently, driven by the watcher's recorded state."""

from __future__ import annotations

import time

import pytest

from kbwizard.win32 import clipboard_watcher


@pytest.fixture
def watcher():
    """Reset the watcher's state before and after each test."""
    clipboard_watcher._forget_watch_state()
    yield
    clipboard_watcher._forget_watch_state()


def test_no_watcher_never_reports_a_recent_change(watcher):
    assert clipboard_watcher.changed_recently(100) is False


def test_marked_sequence_is_not_treated_as_a_change(watcher):
    clipboard_watcher.mark_known_sequence(500)
    assert clipboard_watcher.changed_recently(500) is False


def test_sequence_the_watcher_has_not_seen_yet_counts_as_recent(watcher):
    """The watcher is at most one poll behind, so an unseen sequence must be very recent."""
    clipboard_watcher.mark_known_sequence(500)
    assert clipboard_watcher.changed_recently(501) is True


def test_recorded_change_inside_the_window_counts_as_recent(watcher):
    clipboard_watcher.mark_known_sequence(500)
    now = time.monotonic()
    clipboard_watcher._last_seen_sequence = 501
    clipboard_watcher._last_seen_timestamp = now - (
        clipboard_watcher._RECENT_CHANGE_WINDOW_SECONDS / 2
    )
    clipboard_watcher._last_poll_timestamp = now
    assert clipboard_watcher.changed_recently(501) is True


def test_recorded_change_outside_the_window_is_stale(watcher):
    clipboard_watcher.mark_known_sequence(500)
    now = time.monotonic()
    clipboard_watcher._last_seen_sequence = 501
    clipboard_watcher._last_seen_timestamp = now - (
        clipboard_watcher._RECENT_CHANGE_WINDOW_SECONDS + 1
    )
    clipboard_watcher._last_poll_timestamp = now
    assert clipboard_watcher.changed_recently(501) is False


def test_starved_watcher_is_not_trusted(watcher):
    """A watcher that stopped polling has a baseline of unknown age."""
    clipboard_watcher.mark_known_sequence(500)
    clipboard_watcher._last_poll_timestamp = time.monotonic() - (
        clipboard_watcher._WATCH_STALE_AFTER_SECONDS + 1
    )
    assert clipboard_watcher.changed_recently(501) is False
