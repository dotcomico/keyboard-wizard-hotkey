"""Unit tests for converter.convert and the layout tables."""

from __future__ import annotations

import pytest

from kbwizard.core.converter import REVERSE, _build_reverse, convert
from kbwizard.core.keys import ScanCode
from kbwizard.core.layouts import EN, HE, LAYOUTS


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("vhh", "היי"),
        ("akuo", "שלום"),
        ("AKUO", "שלום"),
        ("AkUo", "שלום"),
        ("t,kv", "אתלה"),
        ("akuo world", "שלום 'םרךג"),
        ("e", "ק"),
        ("`qw;'/.,", ";/'ף,.ץת"),
        ("[]", "]["),
        ("(){}<>", ")(}{><"),
    ],
)
def test_en_to_he(text, expected):
    assert convert(text, "en", "he") == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("שלום", "akuo"),
        ("היי", "vhh"),
        ("שלום world", "akuo world"),
        ("אתלה", "t,kv"),
        ("][", "[]"),
        (")(}{><", "(){}<>"),
    ],
)
def test_he_to_en(text, expected):
    assert convert(text, "he", "en") == expected


@pytest.mark.parametrize(
    "text",
    ["", "123 456", " \n\t", "😀🎉", "€£", "~!@#$%^&*_+-=?\":|\\"],
)
@pytest.mark.parametrize(("src", "tgt"), [("en", "he"), ("he", "en")])
def test_unmapped_chars_pass_through(text, src, tgt):
    assert convert(text, src, tgt) == text


def test_other_scripts_letters_pass_through():
    # Hebrew letters aren't keys of the EN table, and vice versa.
    assert convert("שלום", "en", "he") == "שלום"
    assert convert("hello", "he", "en") == "hello"


def test_mixed_line_keeps_layout_and_newlines():
    assert convert("akuo\n123 vhh", "en", "he") == "שלום\n123 היי"


def test_round_trip_over_every_mapped_en_key():
    every_en = "".join(EN.values())
    assert convert(convert(every_en, "en", "he"), "he", "en") == every_en.lower()


def test_round_trip_uppercase_folds_to_lowercase():
    s = "Hello World"
    assert convert(convert(s, "en", "he"), "he", "en") == s.lower()


@pytest.mark.parametrize("lang", sorted(LAYOUTS))
def test_layout_values_are_unique(lang):
    values = list(LAYOUTS[lang].values())
    assert len(values) == len(set(values))


@pytest.mark.parametrize("lang", sorted(LAYOUTS))
def test_reverse_map_inverts_layout(lang):
    assert {char: stroke for stroke, char in LAYOUTS[lang].items()} == REVERSE[lang]


def test_build_reverse_rejects_duplicate_chars():
    with pytest.raises(ValueError):
        _build_reverse({(ScanCode.A, False): "x", (ScanCode.S, False): "x"})


def test_en_and_he_cover_the_same_keys():
    # A key missing from one side would make conversion silently one-way.
    assert set(EN) == set(HE)


def test_en_has_no_uppercase_entries():
    assert not any(c.isupper() for c in EN.values())


def test_unknown_layout_raises():
    with pytest.raises(KeyError):
        convert("abc", "en", "xx")
