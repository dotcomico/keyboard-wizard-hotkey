"""System tray icon and menu, built on pystray."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from kbwizard import APP_COPYRIGHT, APP_DISPLAY_NAME, APP_NAME, __version__
from kbwizard.app import startup
from kbwizard.app.config import Config
from kbwizard.app.icon_render import render_supersampled
from kbwizard.app.status import NOTIFIES, Status

logger = logging.getLogger(__name__)


def _resource_dir() -> Path:
    """Return the directory that holds ``assets/``, ``LICENSE`` and ``THIRD_PARTY_NOTICES.txt``.

    A PyInstaller one-file build extracts bundled data under ``sys._MEIPASS``.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    # kbwizard/app/tray.py -> project root
    return Path(__file__).resolve().parents[2]


_ICON_PATH = _resource_dir() / "assets" / "icon.ico"
_LICENSE_PATH = _resource_dir() / "LICENSE"
_NOTICES_PATH = _resource_dir() / "THIRD_PARTY_NOTICES.txt"

_LICENSE_SUMMARY = "Free for personal use. Not for sale."


def _load_icon() -> Image.Image:
    if _ICON_PATH.exists():
        return Image.open(_ICON_PATH)
    logger.info("assets/icon.ico not found; using a generated placeholder icon")
    return _fallback_icon()


def _fallback_icon() -> Image.Image:
    """Draw a placeholder "KW" icon for when ``assets/icon.ico`` is missing."""

    def _square(scale: int) -> Image.Image:
        dim = 64 * scale
        inset = 2 * scale
        image = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
        ImageDraw.Draw(image).rounded_rectangle(
            (inset, inset, dim - inset, dim - inset), radius=14 * scale, fill=(38, 110, 210, 255)
        )
        return image

    image = render_supersampled(64, _square)
    # Text is drawn at native size; supersampling PIL's bitmap font only blurs it.
    ImageDraw.Draw(image).text((24, 26), "KW", fill="white")
    return image


class TrayApp:
    """Tray icon and menu shown while the app runs.

    ``on_status`` is called from the hotkey threads; it only updates a label
    and calls pystray methods that post to the icon's own window.
    """

    def __init__(
        self,
        config: Config,
        hotkey_label: str,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        #: Shared with HotkeyController, so a toggle applies on the next press.
        self._config = config
        #: Statuses are hotkey-free, so the tooltip and balloons name the hotkey here.
        self._title = f"{APP_DISPLAY_NAME} ({hotkey_label})"
        self._on_quit = on_quit or (lambda: None)
        self._status = "Starting…"
        #: pystray can't notify or retitle before the icon is shown, so an
        #: earlier status only updates the label.
        self._visible = False
        self._icon = pystray.Icon(
            name=APP_NAME,
            icon=_load_icon(),
            title=self._title,
            menu=pystray.Menu(
                pystray.MenuItem(lambda item: self._status, None, enabled=False),
                pystray.MenuItem(f"Hotkey: {hotkey_label}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Run at startup",
                    self._handle_toggle_startup,
                    checked=lambda item: self._config.run_at_startup,
                ),
                pystray.MenuItem(
                    "Switch keyboard language after convert",
                    self._handle_toggle_switch_layout,
                    checked=lambda item: self._config.switch_layout_after_convert,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("About", self._about_menu()),
                pystray.MenuItem("Quit", self._handle_quit),
            ),
        )

    def _about_menu(self) -> pystray.Menu:
        """Build the About submenu: version, owner, license terms and the full texts."""
        return pystray.Menu(
            pystray.MenuItem(f"{APP_DISPLAY_NAME} {__version__}", None, enabled=False),
            pystray.MenuItem(APP_COPYRIGHT, None, enabled=False),
            pystray.MenuItem(_LICENSE_SUMMARY, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("View license", lambda icon, item: self._open_text(_LICENSE_PATH)),
            pystray.MenuItem(
                "Third-party notices", lambda icon, item: self._open_text(_NOTICES_PATH)
            ),
        )

    def _open_text(self, path: Path) -> None:
        """Open a bundled text file in Notepad.

        Notepad is named explicitly because ``LICENSE`` has no extension, so
        ``os.startfile`` would show the "How do you want to open this file?" dialog.
        """
        try:
            subprocess.Popen(["notepad.exe", str(path)])
        except OSError:
            logger.exception("Could not open %s", path.name)
            self._icon.notify(f"Could not open {path.name}", self._title)

    def on_status(self, status: Status) -> None:
        """Show ``status`` in the tooltip and menu, plus a balloon if it is in ``NOTIFIES``."""
        self._status = status.text
        if not self._visible:
            return
        try:
            self._icon.title = f"{self._title} — {status.text}"
            self._icon.update_menu()
            if status in NOTIFIES:
                self._icon.notify(status.text, self._title)
        except Exception:
            # A tray failure must not take down the worker; the conversion already happened.
            logger.exception("Failed to update the tray for status %s", status.name)

    def run(self, on_ready: Callable[[], None] | None = None) -> None:
        """Show the icon and block until Quit. Must run on the main thread.

        ``on_ready`` runs on pystray's setup thread once the icon is visible, so
        the first status can already show a balloon.
        """

        def _setup(icon: pystray.Icon) -> None:
            # pystray skips its implicit `visible = True` when given a custom setup.
            icon.visible = True
            self._visible = True
            self._icon.title = f"{self._title} — {self._status}"
            if on_ready is not None:
                on_ready()

        self._icon.run(setup=_setup)

    def stop(self) -> None:
        """Hide the icon and unblock ``run()``; safe from any thread and more than once."""
        self._visible = False
        self._icon.stop()

    def _handle_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.stop()
        self._on_quit()

    def _handle_toggle_startup(
        self, icon: pystray.Icon, item: pystray.MenuItem
    ) -> None:
        """Toggle the Run-key entry and persist the setting.

        This runs on pystray's message-loop thread, so registry errors (e.g. a
        policy-locked Run key) are reported instead of raised, and the setting
        is left unchanged. ``update_menu()`` is required because pystray's
        Windows backend only re-evaluates ``checked`` there.
        """
        new_value = not self._config.run_at_startup
        try:
            startup.enable() if new_value else startup.disable()
        except OSError:
            logger.exception("Failed to update the Windows startup registry entry")
            self._icon.notify("Could not update startup setting", self._title)
            self._icon.update_menu()
            return
        self._config.run_at_startup = new_value
        self._config.save()
        self._icon.update_menu()

    def _handle_toggle_switch_layout(
        self, icon: pystray.Icon, item: pystray.MenuItem
    ) -> None:
        """Toggle switching the input language after a conversion, and persist it."""
        self._config.switch_layout_after_convert = not self._config.switch_layout_after_convert
        self._config.save()
        self._icon.update_menu()
