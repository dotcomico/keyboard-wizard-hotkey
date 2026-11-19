"""Per-language tables mapping a physical keystroke to the character it types.

Only keys whose character differs between layouts are listed; everything
else passes through the converter unchanged. English uppercase is omitted
because Shift does not change Hebrew letters, so the converter lowercases
English instead. ``tools/dump_layout.py`` verifies the tables against Windows.
"""

from __future__ import annotations

from kbwizard.core.keys import KeyStroke, ScanCode as K

_UP = False  # no Shift
_SH = True  # Shift held


def _row(pairs: dict[K, str], shift: bool = _UP) -> dict[KeyStroke, str]:
    """Expand ``{scan: char}`` into ``{(scan, shift): char}``."""
    return {(scan, shift): char for scan, char in pairs.items()}


EN: dict[KeyStroke, str] = {
    **_row({
        K.GRAVE: "`",
        K.Q: "q", K.W: "w", K.E: "e", K.R: "r", K.T: "t", K.Y: "y",
        K.U: "u", K.I: "i", K.O: "o", K.P: "p", K.LBRACKET: "[", K.RBRACKET: "]",
        K.A: "a", K.S: "s", K.D: "d", K.F: "f", K.G: "g", K.H: "h",
        K.J: "j", K.K: "k", K.L: "l", K.SEMICOLON: ";", K.APOSTROPHE: "'",
        K.Z: "z", K.X: "x", K.C: "c", K.V: "v", K.B: "b", K.N: "n",
        K.M: "m", K.COMMA: ",", K.PERIOD: ".", K.SLASH: "/",
    }),
    **_row({
        K.DIGIT9: "(", K.DIGIT0: ")",
        K.LBRACKET: "{", K.RBRACKET: "}",
        K.COMMA: "<", K.PERIOD: ">",
    }, _SH),
}

# Israeli standard (SI-1452 as shipped by Windows, KBDHEB).
HE: dict[KeyStroke, str] = {
    **_row({
        K.GRAVE: ";",
        K.Q: "/", K.W: "'", K.E: "ק", K.R: "ר", K.T: "א", K.Y: "ט",
        K.U: "ו", K.I: "ן", K.O: "ם", K.P: "פ", K.LBRACKET: "]", K.RBRACKET: "[",
        K.A: "ש", K.S: "ד", K.D: "ג", K.F: "כ", K.G: "ע", K.H: "י",
        K.J: "ח", K.K: "ל", K.L: "ך", K.SEMICOLON: "ף", K.APOSTROPHE: ",",
        K.Z: "ז", K.X: "ס", K.C: "ב", K.V: "ה", K.B: "נ", K.N: "מ",
        K.M: "צ", K.COMMA: "ת", K.PERIOD: "ץ", K.SLASH: ".",
    }),
    # Hebrew is RTL, so Windows mirrors the paired symbols on these keys.
    **_row({
        K.DIGIT9: ")", K.DIGIT0: "(",
        K.LBRACKET: "}", K.RBRACKET: "{",
        K.COMMA: ">", K.PERIOD: "<",
    }, _SH),
}

LAYOUTS: dict[str, dict[KeyStroke, str]] = {
    "en": EN,
    "he": HE,
}

#: Windows LANGID of the layout each table describes (en-US, he-IL).
LANGIDS: dict[str, int] = {"en": 0x0409, "he": 0x040D}
