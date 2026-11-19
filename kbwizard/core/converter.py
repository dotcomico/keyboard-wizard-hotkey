"""Converts text between keyboard layouts by physical key position."""

from __future__ import annotations

from kbwizard.core.keys import KeyStroke
from kbwizard.core.layouts import LAYOUTS

_HEBREW_FIRST = "א"
_HEBREW_LAST = "ת"


def _build_reverse(layout: dict[KeyStroke, str]) -> dict[str, KeyStroke]:
    """Invert a layout table; a character typed by two keys is rejected as ambiguous."""
    reverse: dict[str, KeyStroke] = {}
    for stroke, char in layout.items():
        if char in reverse:
            raise ValueError(f"{char!r} is mapped by both {reverse[char]} and {stroke}")
        reverse[char] = stroke
    return reverse


# Built once at import; convert() runs on every hotkey press.
REVERSE: dict[str, dict[str, KeyStroke]] = {
    lang: _build_reverse(layout) for lang, layout in LAYOUTS.items()
}


def _is_ascii_letter(char: str) -> bool:
    return char.isascii() and char.isalpha()


def _is_hebrew_letter(char: str) -> bool:
    return _HEBREW_FIRST <= char <= _HEBREW_LAST


def _source_key(char: str, source: str) -> str:
    # Hebrew letters ignore Shift/Caps, so English case carries no information.
    return char.lower() if source == "en" and _is_ascii_letter(char) else char


def convert(text: str, source: str, target: str) -> str:
    """Retype ``text`` as if the same physical keys were pressed under ``target``.

    Characters ``source`` cannot type (digits, spaces, emoji, the other
    script) pass through unchanged, so mixed-language text is safe.

    Raises:
        KeyError: If ``source`` or ``target`` is not a known layout.
    """
    reverse = REVERSE[source]
    target_layout = LAYOUTS[target]
    out = []
    for char in text:
        stroke = reverse.get(_source_key(char, source))
        out.append(target_layout.get(stroke, char) if stroke is not None else char)
    return "".join(out)


def count_scripts(text: str) -> tuple[int, int]:
    """Return ``(hebrew, latin)`` letter counts for ``text``."""
    hebrew = sum(1 for c in text if _is_hebrew_letter(c))
    latin = sum(1 for c in text if _is_ascii_letter(c))
    return hebrew, latin


def detect_direction(text: str) -> tuple[str, str]:
    """Return the ``(source, target)`` layout names for ``text``.

    Hebrew wins ties: a selection with as much Hebrew as Latin was most
    likely typed on the Hebrew layout. Text with no letters defaults to EN->HE.
    """
    hebrew, latin = count_scripts(text)
    if hebrew > 0 and hebrew >= latin:
        return "he", "en"
    return "en", "he"
