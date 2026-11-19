"""Entry point: single-instance guard, logging, and wiring of the tray and hotkey.

Threads: the main thread runs the pystray loop; pystray's setup thread
starts the hotkey once the icon is visible; the hotkey listener runs its
own message loop; each press is handled on a worker thread; the clipboard
watcher polls on its own thread.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The dev-mode Run-key entry starts this file as a script (cwd = System32),
# so make the package importable.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ctypes  # noqa: E402
import logging  # noqa: E402
import threading  # noqa: E402
from logging.handlers import RotatingFileHandler  # noqa: E402

from kbwizard import APP_DISPLAY_NAME, APP_NAME, __version__  # noqa: E402
from kbwizard.app import startup  # noqa: E402
from kbwizard.app.config import Config, app_dir  # noqa: E402
from kbwizard.app.controller import HotkeyController  # noqa: E402
from kbwizard.app.status import Status  # noqa: E402
from kbwizard.app.tray import TrayApp  # noqa: E402
from kbwizard.win32.hotkey import HotkeyUnavailable, format_hotkey  # noqa: E402

logger = logging.getLogger("kbwizard")

_MUTEX_NAME = f"Local\\{APP_NAME}Hotkey"
_ERROR_ALREADY_EXISTS = 183
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(threadName)s]: %(message)s"

#: Held for the process lifetime; Windows frees a named mutex when its
#: last handle closes.
_mutex_handle: int | None = None


def _set_dpi_aware() -> None:
    """Enable per-monitor DPI awareness; must run before any window is created.

    Without it, Windows stretches the tray icon on scaled displays and it looks blurry.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            logger.warning(
                "Could not set DPI awareness; the tray icon may look stretched "
                "on a scaled display."
            )


def _setup_logging() -> None:
    """Log to a rotating file in the app directory, and to the console if there is one."""
    log_dir = app_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_dir / "kbwizard.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
    ]
    # pythonw and the windowed exe have no stderr to stream to.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, handlers=handlers)


def _log_uncaught_exceptions() -> None:
    """Send uncaught exceptions from any thread to the log, since there is no console."""

    def _main_hook(exc_type, exc, tb) -> None:
        logger.critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        logger.critical(
            "Uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _main_hook
    threading.excepthook = _thread_hook


def _acquire_single_instance() -> bool:
    """Create the app's named mutex; return False if another instance holds it."""
    global _mutex_handle
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS


def _sync_startup_flag(config: Config) -> None:
    """Sync ``config.run_at_startup`` with the Run key, which Task Manager can change."""
    actual = startup.is_enabled()
    if config.run_at_startup != actual:
        config.run_at_startup = actual
        config.save()


def main() -> None:
    """Run the app until Quit is chosen from the tray menu."""
    _setup_logging()
    _log_uncaught_exceptions()
    if not _acquire_single_instance():
        logger.info("Another %s instance is already running; exiting.", APP_DISPLAY_NAME)
        return
    _set_dpi_aware()

    config = Config.load()
    _sync_startup_flag(config)
    logger.info(
        "%s %s starting (config: %s)", APP_DISPLAY_NAME, __version__, Config.config_path()
    )

    # One shared Config, so a tray toggle applies on the next press. The tray
    # needs the controller's validated hotkey for its title, so the controller
    # is built first with a late-bound status callback.
    hotkey = HotkeyController(config, on_status=lambda status: tray.on_status(status))
    tray = TrayApp(
        config,
        hotkey_label=format_hotkey(hotkey.hotkey),
        on_quit=lambda: logger.info("Quit selected from the tray menu"),
    )

    def on_ready() -> None:
        try:
            hotkey.start()
        except HotkeyUnavailable:
            logger.warning("Hotkey %s is already registered by another app", hotkey.hotkey)
            tray.on_status(Status.HOTKEY_UNAVAILABLE)
        except Exception:
            # Unexpected failure; the status tells the user to check the log.
            logger.exception("Could not start the hotkey")
            tray.on_status(Status.CONVERT_FAILED)

    try:
        tray.run(on_ready=on_ready)
    finally:
        hotkey.stop()
        logger.info("%s stopped", APP_DISPLAY_NAME)


if __name__ == "__main__":
    main()
