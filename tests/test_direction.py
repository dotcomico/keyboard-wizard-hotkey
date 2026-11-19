"""Unit tests for converter.detect_direction and count_scripts."""

from __future__ import annotations

import pytest

from kbwizard.core.converter import count_scripts, detect_direction


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", (0, 0)),
        ("abc", (0, 3)),
        ("ABC xyz", (0, 6)),
        ("שלום", (4, 0)),
        ("שלום world", (4, 5)),
        ("123 !? \n😀", (0, 0)),
        ("éñ", (0, 0)),  # non-ASCII Latin isn't on the EN layout
        ("ְ׳", (0, 0)),  # niqqud / geresh are outside U+05D0-U+05EA
    ],
)
def test_count_scripts(text, expected):
    assert count_scripts(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("akuo", ("en", "he")),
        ("vhh", ("en", "he")),
        ("שלום", ("he", "en")),
        ("שלום world", ("en", "he")),  # 4 Hebrew < 5 Latin
        ("שלום ab", ("he", "en")),
        ("אב ab", ("he", "en")),  # tie -> Hebrew wins
        ("", ("en", "he")),
        ("123 !?", ("en", "he")),  # no letters -> default EN->HE
        ("t,kv", ("en", "he")),
    ],
)
def test_detect_direction(text, expected):
    assert detect_direction(text) == expected
