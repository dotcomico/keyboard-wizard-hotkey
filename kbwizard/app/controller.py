"""Per-press pipeline: capture the selection, convert it, paste it back, switch layout."""

from __future__ import annotations

import logging
import threading
from typing import Callable

from kbwizard.app.config import DEFAULT_HOTKEY, Config
from kbwizard.app.state import StateMachine
from kbwizard.app.status import Status
from kbwizard.core import converter
from kbwizard.win32 import clipboard_io, clipboard_watcher, layout_switch, window, winput
from kbwizard.win32.hotkey import HotkeyListener, parse_hotkey

logger = logging.getLogger(__name__)

#: Seconds to wait for the user to release the hotkey before injecting Ctrl+C.
_KEY_RELEASE_TIMEOUT = 1.0


def _valid_or_default(spec: str) -> str:
    """Return ``spec`` if it parses, else the default, so a config typo never disables the hotkey."""
    try:
        parse_hotkey(spec)
    except ValueError:
        logger.warning("Invalid hotkey %r in config.json; using %s", spec, DEFAULT_HOTKEY)
        return DEFAULT_HOTKEY
    return spec


class HotkeyController:
    """Runs the conversion pipeline on each hotkey press.

    The listener thread only records the foreground window and claims the
    busy guard; the clipboard and ``SendInput`` work runs on a worker thread
    so the message loop stays responsive. One press is processed at a time.
    """

    def __init__(
        self,
        config: Config,
        on_status: Callable[[Status], None] | None = None,
    ) -> None:
        self._config = config
        self._on_status = on_status or (lambda status: logger.info(status.text))
        self._state = StateMachine()
        self._listener: HotkeyListener | None = None
        self._hotkey = _valid_or_default(config.hotkey)
        self._vk = 0

    @property
    def hotkey(self) -> str:
        """The hotkey spec in use: ``config.hotkey``, or the default if that is malformed."""
        return self._hotkey

    def start(self) -> None:
        """Start the clipboard watcher and register the hotkey.

        Raises:
            HotkeyUnavailable: If another app owns the combo. The watcher is
                stopped before raising.
        """
        clipboard_watcher.start_watching()
        try:
            mods, self._vk = parse_hotkey(self._hotkey)
            listener = HotkeyListener(mods, self._vk, self._on_hotkey)
            listener.start()
        except Exception:
            clipboard_watcher.stop_watching()
            raise
        self._listener = listener
        logger.info("Listening for %s", self._hotkey)
        self._on_status(Status.READY)

    def stop(self) -> None:
        """Unregister the hotkey and stop the clipboard watcher."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        clipboard_watcher.stop_watching()

    def _on_hotkey(self) -> None:
        """Handle a press on the listener thread; must return quickly."""
        # Recorded at press time so the focus guard can detect a window switch.
        hwnd = window.foreground_window()
        if not self._state.try_begin():
            return  # busy: drop the press rather than queue it
        threading.Thread(target=self._run_cycle, args=(hwnd,), daemon=True).start()

    def _run_cycle(self, hwnd: int) -> None:
        """Process one press. Config is read here because the tray can change it live."""
        try:
            self._wait_for_hotkey_release()

            text = clipboard_io.capture_selected_text()
            if not text:
                self._on_status(Status.NO_TEXT_SELECTED)
                return

            source, target = converter.detect_direction(text)
            result = converter.convert(text, source, target)
            if result == text:
                self._on_status(Status.NOTHING_TO_CONVERT)
                return

            # Never paste into a window the user switched to during capture.
            if window.foreground_window() != hwnd:
                self._on_status(Status.FOCUS_CHANGED)
                return

            clipboard_io.replace_selection(
                result, keep_on_clipboard=self._config.keep_result_on_clipboard
            )
            # Length and direction only, never the text.
            logger.info("Converted %d chars %s->%s", len(text), source, target)

            if self._config.switch_layout_after_convert:
                switched = layout_switch.switch_foreground_to(target)
                if switched is layout_switch.SwitchResult.NOT_INSTALLED:
                    self._on_status(Status.layout_missing(target))
                    return
            self._on_status(Status.converted_to(target))
        except Exception:
            logger.exception("Convert cycle failed")
            self._on_status(Status.CONVERT_FAILED)
        finally:
            self._state.reset_to_idle()

    def _wait_for_hotkey_release(self) -> None:
        """Wait for the hotkey keys to be released, forcing key-ups on timeout.

        Injected input merges with the physical keyboard state, so a held Alt
        would turn the injected Ctrl+C into Ctrl+Alt+C.
        """
        vks = tuple(winput.HOTKEY_MODIFIER_VKS) + (self._vk,)
        if not winput.wait_for_keys_released(vks, _KEY_RELEASE_TIMEOUT):
            stuck = winput.keys_still_down(vks)
            logger.warning(
                "Hotkey keys still held after %.1fs; forcing release", _KEY_RELEASE_TIMEOUT
            )
            winput.release_keys(stuck)
