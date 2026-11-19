"""Checks the layout tables against the installed EN/HE layouts; skipped if either is missing."""

from __future__ import annotations

import sys

import pytest

from kbwizard.core.layouts import LANGIDS, LAYOUTS

if sys.platform != "win32":
    pytest.skip("Windows-only: queries the OS keyboard layouts", allow_module_level=True)

from tools.dump_layout import os_layout_table  # noqa: E402


@pytest.fixture(scope="module")
def os_tables():
    tables = {lang: os_layout_table(langid) for lang, langid in LANGIDS.items()}
    missing = [lang for lang, table in tables.items() if table is None]
    if missing:
        pytest.skip(f"keyboard layout(s) not installed: {', '.join(missing)}")
    return tables


@pytest.mark.parametrize("lang", sorted(LANGIDS))
def test_every_cell_matches_os(os_tables, lang):
    os_table = os_tables[lang]
    mismatches = {
        stroke: (ours, os_table.get(stroke))
        for stroke, ours in LAYOUTS[lang].items()
        if os_table.get(stroke) != ours
    }
    assert mismatches == {}


def test_every_differing_key_is_mapped(os_tables):
    # Keys that differ between EN and HE must be mapped, or the converter
    # would leave them unconverted. Shifted letters are exempt: English is
    # lowercased instead.
    en, he = os_tables["en"], os_tables["he"]
    mapped = set(LAYOUTS["en"])
    unmapped = [
        stroke
        for stroke in set(en) & set(he)
        if en[stroke] != he[stroke] and stroke not in mapped
        and not (stroke[1] and en[stroke].isalpha())
    ]
    assert unmapped == []
