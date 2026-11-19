"""User-facing status messages and which of them show a tray notification."""

from __future__ import annotations

from enum import Enum


class Status(Enum):
    """A pipeline status whose value is its display text."""

    READY = "Ready."
    CONVERTED_TO_HE = "Converted to Hebrew."
    CONVERTED_TO_EN = "Converted to English."
    NO_TEXT_SELECTED = "No text selected."
    NOTHING_TO_CONVERT = "Nothing to convert."
    FOCUS_CHANGED = "Window changed — nothing pasted."
    LAYOUT_NOT_INSTALLED_HE = "Converted, but the Hebrew keyboard isn't installed."
    LAYOUT_NOT_INSTALLED_EN = "Converted, but the English keyboard isn't installed."
    HOTKEY_UNAVAILABLE = "The hotkey is used by another app."
    CONVERT_FAILED = "Conversion failed — see log."

    @property
    def text(self) -> str:
        return self.value

    @classmethod
    def converted_to(cls, lang: str) -> "Status":
        """Return the success status for a conversion into ``lang``."""
        return cls.CONVERTED_TO_HE if lang == "he" else cls.CONVERTED_TO_EN

    @classmethod
    def layout_missing(cls, lang: str) -> "Status":
        """Return the status for a conversion whose target layout isn't installed."""
        return cls.LAYOUT_NOT_INSTALLED_HE if lang == "he" else cls.LAYOUT_NOT_INSTALLED_EN


#: Statuses that show a balloon; the rest only update the tooltip and menu.
NOTIFIES: set[Status] = {
    Status.NO_TEXT_SELECTED,
    Status.NOTHING_TO_CONVERT,
    Status.FOCUS_CHANGED,
    Status.LAYOUT_NOT_INSTALLED_HE,
    Status.LAYOUT_NOT_INSTALLED_EN,
    Status.HOTKEY_UNAVAILABLE,
    Status.CONVERT_FAILED,
}
