"""Unit tests for clipboard_io's capture and replace, run over the real watcher.

``win32clipboard`` and ``winput`` are replaced with fakes so a test can
place a clipboard write at an exact moment relative to a capture or replace.
"""

from __future__ import annotations

import time

import pytest

from kbwizard.win32 import clipboard_io, clipboard_watcher

CF_UNICODETEXT = 13


class FakeClipboard:
    """Stand-in for ``win32clipboard``.

    Like the real API, the sequence number increments on every write
    (``EmptyClipboard`` and ``SetClipboardData`` alike), even when the
    content is unchanged.
    """

    def __init__(self) -> None:
        self._seq = 100
        self.formats: dict[int, object] = {}
        self._registered: dict[str, int] = {}
        #: What a Ctrl+C in the focused app would copy. ``None`` models a
        #: copy-on-select terminal that already consumed the selection,
        #: so the simulated Ctrl+C produces no clipboard write at all.
        self.selection: str | None = None
        #: How many Ctrl+C presses were injected.
        self.copies = 0
        #: Snapshot of `formats` after each clipboard session that wrote something.
        self.writes: list[dict[int, object]] = []
        #: Ordered log of events across clipboard and fake input.
        self.events: list[str] = []
        self._dirty = False

    @property
    def text(self) -> str | None:
        return self.formats.get(CF_UNICODETEXT)  # type: ignore[return-value]

    def GetClipboardSequenceNumber(self) -> int:
        return self._seq

    def OpenClipboard(self) -> None:
        self._dirty = False

    def CloseClipboard(self) -> None:
        if self._dirty:
            self.writes.append(dict(self.formats))
            self.events.append(f"write:{self.text}")
        self._dirty = False

    def IsClipboardFormatAvailable(self, fmt: int) -> bool:
        return fmt in self.formats

    def GetClipboardData(self, fmt: int) -> object:
        return self.formats.get(fmt)

    def EmptyClipboard(self) -> None:
        self._seq += 1
        self.formats.clear()
        self._dirty = True

    def SetClipboardData(self, fmt: int, data: object) -> None:
        self._seq += 1
        self.formats[fmt] = data
        self._dirty = True

    def RegisterClipboardFormat(self, name: str) -> int:
        return self._registered.setdefault(name, 0xC000 + len(self._registered))

    def external_write(self, text: str) -> None:
        """Simulate a write by another process, e.g. a terminal's copy-on-select."""
        self._seq += 1
        self.formats = {CF_UNICODETEXT: text}

    def format_id(self, name: str) -> int:
        return self.RegisterClipboardFormat(name)


class FakeWinput:
    """Stand-in for ``winput``'s injection functions."""

    def __init__(self, clipboard: FakeClipboard) -> None:
        self._clipboard = clipboard
        self.pasted: list[str | None] = []
        self.paste_error: Exception | None = None

    def send_copy(self) -> None:
        clip = self._clipboard
        clip.copies += 1
        clip.events.append("copy")
        if clip.selection is None:
            return  # nothing left to copy, so no clipboard write
        clip.EmptyClipboard()
        clip.SetClipboardData(CF_UNICODETEXT, clip.selection)
        clip._dirty = False  # another app's write

    def send_paste(self) -> None:
        self._clipboard.events.append("paste")
        if self.paste_error is not None:
            raise self.paste_error
        self.pasted.append(self._clipboard.text)


@pytest.fixture
def clip(monkeypatch):
    """Provide a fake clipboard, resetting watcher state before and after each test."""
    clipboard = FakeClipboard()
    fake_input = FakeWinput(clipboard)
    clipboard.input = fake_input  # type: ignore[attr-defined]
    monkeypatch.setattr(clipboard_io, "win32clipboard", clipboard)
    monkeypatch.setattr(clipboard_watcher, "win32clipboard", clipboard)
    monkeypatch.setattr(clipboard_io, "winput", fake_input)
    monkeypatch.setattr(clipboard_io, "_registered_format_ids", {})
    monkeypatch.setattr(clipboard_io, "_COPY_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(clipboard_io, "_POLL_INTERVAL_SECONDS", 0.005)
    clipboard_watcher._forget_watch_state()
    yield clipboard
    clipboard_watcher.stop_watching()
    clipboard_watcher._forget_watch_state()


@pytest.fixture
def no_settle(monkeypatch, clip):
    """Replace the paste-settle sleep with a recorded no-op; other sleeps pass through."""
    real_sleep = time.sleep

    def fake_sleep(seconds: float) -> None:
        if seconds == clipboard_io._PASTE_SETTLE_SECONDS:
            clip.events.append("settle")
        else:
            real_sleep(seconds)

    monkeypatch.setattr(clipboard_io.time, "sleep", fake_sleep)
    return clip


def _use_fast_polling(monkeypatch) -> None:
    """Make the watcher poll every few milliseconds instead of every 200."""
    monkeypatch.setattr(clipboard_watcher, "_WATCH_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(clipboard_watcher, "_WATCH_STALE_AFTER_SECONDS", 0.5)


def _freeze_polling(monkeypatch) -> None:
    """Stop the watcher polling after its initial prime, to land a press inside the poll gap."""
    monkeypatch.setattr(clipboard_watcher, "_WATCH_POLL_INTERVAL_SECONDS", 60.0)
    monkeypatch.setattr(clipboard_watcher, "_WATCH_STALE_AFTER_SECONDS", 60.0)


def _wait_for_poll() -> None:
    time.sleep(0.05)


def _has_history_exclusion(snapshot: dict[int, object], clip: FakeClipboard) -> bool:
    return (
        clip.format_id("ExcludeClipboardContentFromMonitorProcessing") in snapshot
        and snapshot.get(clip.format_id("CanIncludeInClipboardHistory"))
        == b"\x00\x00\x00\x00"
        and snapshot.get(clip.format_id("CanUploadToCloudClipboard"))
        == b"\x00\x00\x00\x00"
    )


def test_copy_on_select_text_is_used_without_sending_ctrl_c(clip, monkeypatch):
    """A terminal copied the selection before the hotkey, so a Ctrl+C would find nothing."""
    _use_fast_polling(monkeypatch)
    clipboard_watcher.start_watching()
    _wait_for_poll()

    clip.external_write("copied on select")
    _wait_for_poll()
    sequence_before = clip.GetClipboardSequenceNumber()

    assert clipboard_io.capture_selected_text() == "copied on select"
    assert clip.copies == 0, "should not send a Ctrl+C it doesn't need"
    assert clip.GetClipboardSequenceNumber() == sequence_before, (
        "fast path must not touch the clipboard, so nothing needs restoring"
    )


def test_copy_on_select_detected_inside_the_watcher_poll_gap(clip, monkeypatch):
    """A change the watcher hasn't polled yet must still count as recent."""
    _freeze_polling(monkeypatch)
    clipboard_watcher.start_watching()

    clip.external_write("copied on select")  # watcher will not poll again

    assert clipboard_io.capture_selected_text() == "copied on select"
    assert clip.copies == 0


def test_one_auto_copy_is_consumed_only_once(clip, monkeypatch):
    """A second press must read the new selection rather than replay the first auto-copy."""
    _use_fast_polling(monkeypatch)
    clipboard_watcher.start_watching()
    _wait_for_poll()

    clip.external_write("first selection")
    _wait_for_poll()
    assert clipboard_io.capture_selected_text() == "first selection"

    clip.selection = "second selection"
    assert clipboard_io.capture_selected_text() == "second selection"
    assert clip.copies == 1, "second press must fall back to Ctrl+C"


def test_normal_app_uses_ctrl_c_and_restores_the_clipboard(clip, monkeypatch):
    _use_fast_polling(monkeypatch)
    clipboard_watcher.start_watching()
    clip.external_write("user's own clipboard")
    _wait_for_poll()
    time.sleep(clipboard_watcher._RECENT_CHANGE_WINDOW_SECONDS + 0.05)

    clip.selection = "highlighted text"

    assert clipboard_io.capture_selected_text() == "highlighted text"
    assert clip.copies == 1
    assert clip.text == "user's own clipboard", "clipboard must be restored"


def test_capture_restore_is_excluded_from_history(clip):
    clip.external_write("user's own clipboard")
    clip.selection = "highlighted text"

    assert clipboard_io.capture_selected_text() == "highlighted text"
    assert _has_history_exclusion(clip.writes[-1], clip)


def test_own_restore_is_not_mistaken_for_an_external_change(clip, monkeypatch):
    """The capture's own restore write must not look like a fresh selection to the next press."""
    _use_fast_polling(monkeypatch)
    clipboard_watcher.start_watching()
    clip.external_write("user's own clipboard")
    _wait_for_poll()
    time.sleep(clipboard_watcher._RECENT_CHANGE_WINDOW_SECONDS + 0.05)

    clip.selection = "first selection"
    assert clipboard_io.capture_selected_text() == "first selection"

    clip.selection = "second selection"
    assert clipboard_io.capture_selected_text() == "second selection"
    assert clip.copies == 2


def test_stale_clipboard_is_not_replayed_as_a_selection(clip, monkeypatch):
    _use_fast_polling(monkeypatch)
    clipboard_watcher.start_watching()
    clip.external_write("copied ages ago")
    _wait_for_poll()
    time.sleep(clipboard_watcher._RECENT_CHANGE_WINDOW_SECONDS + 0.05)

    assert clipboard_io.capture_selected_text() is None
    assert clip.text == "copied ages ago", "clipboard must survive a failed capture"


def test_clipboard_present_at_startup_is_not_replayed(clip, monkeypatch):
    _freeze_polling(monkeypatch)
    clip.external_write("copied before KeyboardWizard started")
    clipboard_watcher.start_watching()

    assert clipboard_io.capture_selected_text() is None
    assert clip.copies == 1


def test_replace_writes_then_pastes_then_settles_then_restores(no_settle):
    clip = no_settle
    clip.external_write("user's own clipboard")

    clipboard_io.replace_selection("converted")

    assert clip.events == [
        "write:converted",
        "paste",
        "settle",
        "write:user's own clipboard",
    ]
    assert clip.input.pasted == ["converted"]  # type: ignore[attr-defined]
    assert clip.text == "user's own clipboard"


def test_replace_restores_even_when_paste_fails(no_settle):
    clip = no_settle
    clip.external_write("user's own clipboard")
    clip.input.paste_error = OSError(5, "access denied")  # type: ignore[attr-defined]

    with pytest.raises(OSError):
        clipboard_io.replace_selection("converted")

    assert clip.text == "user's own clipboard"
    assert clip.events[-1] == "write:user's own clipboard"


def test_keep_on_clipboard_skips_the_restore(no_settle):
    clip = no_settle
    clip.external_write("user's own clipboard")

    clipboard_io.replace_selection("converted", keep_on_clipboard=True)

    assert clip.text == "converted"
    assert clip.events == ["write:converted", "paste", "settle"]


def test_both_replace_writes_are_excluded_from_history(no_settle):
    clip = no_settle
    clip.external_write("user's own clipboard")

    clipboard_io.replace_selection("converted")

    assert len(clip.writes) == 2
    assert all(_has_history_exclusion(w, clip) for w in clip.writes)


def test_empty_original_clipboard_is_cleared_on_restore(no_settle):
    clip = no_settle
    assert clip.text is None

    clipboard_io.replace_selection("converted")

    assert clip.formats == {}, "no text and no stray tag formats left behind"


def test_format_registration_failure_never_blocks_the_write(no_settle, monkeypatch):
    clip = no_settle

    def broken(name: str) -> int:
        raise RuntimeError("registration failed")

    monkeypatch.setattr(clip, "RegisterClipboardFormat", broken)
    clip.external_write("user's own clipboard")

    clipboard_io.replace_selection("converted")

    assert clip.input.pasted == ["converted"]  # type: ignore[attr-defined]
    assert clip.text == "user's own clipboard"


def test_capture_after_replace_takes_the_ctrl_c_path(no_settle, monkeypatch):
    """Both replace writes are reported to the watcher, so the next capture still sends Ctrl+C."""
    clip = no_settle
    _use_fast_polling(monkeypatch)
    clipboard_watcher.start_watching()
    clip.external_write("user's own clipboard")
    _wait_for_poll()
    time.sleep(clipboard_watcher._RECENT_CHANGE_WINDOW_SECONDS + 0.05)

    clipboard_io.replace_selection("converted")

    clip.selection = "next selection"
    assert clipboard_io.capture_selected_text() == "next selection"
    assert clip.copies == 1


def test_capture_after_kept_replace_takes_the_ctrl_c_path(no_settle, monkeypatch):
    """With keep_on_clipboard, the text left on the clipboard is still the app's own write."""
    clip = no_settle
    _freeze_polling(monkeypatch)
    clipboard_watcher.start_watching()

    clipboard_io.replace_selection("converted", keep_on_clipboard=True)

    clip.selection = "next selection"
    assert clipboard_io.capture_selected_text() == "next selection"
    assert clip.copies == 1
