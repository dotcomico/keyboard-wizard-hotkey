"""Persisted settings, stored as JSON in the per-user app directory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from kbwizard import APP_NAME

DEFAULT_HOTKEY = "ctrl+alt+w"


def app_dir() -> Path:
    """Return ``%APPDATA%/KeyboardWizard`` (config and log), or a home-directory fallback."""
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    return base / APP_NAME


@dataclass
class Config:
    """Persisted user settings."""

    #: Editable only in config.json.
    hotkey: str = DEFAULT_HOTKEY
    #: Cached Run-key state so the tray renders without a registry read;
    #: the registry remains the source of truth.
    run_at_startup: bool = False
    #: After pasting, switch the window's input language to the target.
    switch_layout_after_convert: bool = True
    #: Leave the converted text on the clipboard instead of restoring the
    #: original (config.json only).
    keep_result_on_clipboard: bool = False

    @staticmethod
    def config_path() -> Path:
        """Return the path of the settings file."""
        return app_dir() / "config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load settings from disk, creating defaults on first run.

        Unknown keys are dropped, missing keys get defaults, and a corrupt file
        is reset instead of crashing the app.
        """
        path = cls.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            config = cls()
            config.save()
            return config

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config root is not an object")
        except (json.JSONDecodeError, OSError, ValueError):
            config = cls()
            config.save()
            return config

        defaults = asdict(cls())
        merged = {**defaults, **{k: v for k, v in raw.items() if k in defaults}}
        return cls(**merged)

    def save(self) -> None:
        """Write the settings to disk as JSON."""
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
