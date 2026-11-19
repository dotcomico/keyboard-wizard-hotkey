"""Diff the layout tables against the keyboard layouts installed in Windows.

Only installed layouts are queried; ``LoadKeyboardLayout`` is never called.

Usage: .venv/Scripts/python.exe tools/dump_layout.py
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Make the project root importable when run as a script.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kbwizard.core.keys import KeyStroke, ScanCode  # noqa: E402
from kbwizard.core.layouts import LANGIDS, LAYOUTS  # noqa: E402

_MAPVK_VSC_TO_VK = 1
_VK_SHIFT = 0x10
_KEY_DOWN = 0x80
# Windows 10 1607+: leave the keyboard state alone, so probing a dead key
# can't corrupt the user's next keystroke.
_TOUNICODE_NO_STATE_CHANGE = 0x4


def _user32() -> ctypes.WinDLL:
    # Private instance so these argtypes can't clash with other modules'.
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HKL]
    user32.MapVirtualKeyExW.restype = wintypes.UINT
    user32.ToUnicodeEx.argtypes = [
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.HKL,
    ]
    user32.ToUnicodeEx.restype = ctypes.c_int
    return user32


def installed_layouts() -> list[int]:
    """Return the HKLs in the user's input-language list (empty off Windows)."""
    if sys.platform != "win32":
        return []
    # Deferred: the Win32 layer loads user32 at import, which fails off Windows.
    from kbwizard.win32.layout_switch import installed_layouts as app_installed_layouts

    return app_installed_layouts()


def find_layout(langid: int) -> int | None:
    """Return the first installed HKL whose LANGID is exactly ``langid``, else None."""
    for hkl in installed_layouts():
        if hkl & 0xFFFF == langid:
            return hkl
    return None


def _char_for(user32: ctypes.WinDLL, hkl: int, scan: int, shift: bool) -> str | None:
    """Return the single character ``scan`` types under ``hkl``, else None.

    Dead keys, ligatures and keys that type nothing return None, since none
    of them can be a one-to-one conversion cell.
    """
    vk = user32.MapVirtualKeyExW(scan, _MAPVK_VSC_TO_VK, hkl)
    if not vk:
        return None
    state = (ctypes.c_ubyte * 256)()
    if shift:
        state[_VK_SHIFT] = _KEY_DOWN
    buf = ctypes.create_unicode_buffer(8)
    rc = user32.ToUnicodeEx(vk, scan, state, buf, len(buf), _TOUNICODE_NO_STATE_CHANGE, hkl)
    return buf.value[0] if rc == 1 else None


def os_layout_table(langid: int) -> dict[KeyStroke, str] | None:
    """Return what each ``ScanCode`` key types under ``langid``'s layout; None if not installed."""
    hkl = find_layout(langid)
    if hkl is None:
        return None
    user32 = _user32()
    table: dict[KeyStroke, str] = {}
    for scan in ScanCode:
        for shift in (False, True):
            char = _char_for(user32, hkl, scan, shift)
            if char is not None:
                table[(scan, shift)] = char
    return table


def _label(stroke: KeyStroke) -> str:
    scan, shift = stroke
    return f"{scan.name:<10} ({int(scan):>2}){' +shift' if shift else '       '}"


def _print_side_by_side(os_tables: dict[str, dict[KeyStroke, str] | None]) -> None:
    print(f"{'key':<24}" + "".join(f"{lang:>6}" for lang in os_tables))
    for scan in ScanCode:
        for shift in (False, True):
            stroke = (scan, shift)
            cells = [(t or {}).get(stroke, "-") for t in os_tables.values()]
            print(f"{_label(stroke):<24}" + "".join(f"{c:>6}" for c in cells))


def _diff(lang: str, os_table: dict[KeyStroke, str]) -> list[str]:
    """Return the cells where the table for ``lang`` disagrees with the OS."""
    problems = []
    for stroke, ours in LAYOUTS[lang].items():
        real = os_table.get(stroke)
        if real != ours:
            problems.append(f"{lang} {_label(stroke)}: ours={ours!r} os={real!r}")
    return problems


def _missing(en: dict[KeyStroke, str], he: dict[KeyStroke, str]) -> list[str]:
    """Return keys that differ between the OS layouts but are not mapped.

    Shifted English letters are skipped because the converter lowercases them.
    """
    mapped = set(LAYOUTS["en"]) | set(LAYOUTS["he"])
    notes = []
    for stroke in sorted(set(en) & set(he)):
        if en[stroke] != he[stroke] and stroke not in mapped:
            if stroke[1] and en[stroke].isalpha():
                continue
            notes.append(f"unmapped {_label(stroke)}: en={en[stroke]!r} he={he[stroke]!r}")
    return notes


def main() -> int:
    """Print the OS layouts side by side and report mismatches; exit code 1 if any."""
    if sys.platform != "win32":
        print("Windows only.")
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    os_tables = {lang: os_layout_table(langid) for lang, langid in LANGIDS.items()}
    for lang, table in os_tables.items():
        if table is None:
            print(f"[{lang}] layout 0x{LANGIDS[lang]:04X} is not installed -- skipped.")
    _print_side_by_side(os_tables)

    problems: list[str] = []
    for lang, table in os_tables.items():
        if table is not None:
            problems += _diff(lang, table)
    if os_tables["en"] is not None and os_tables["he"] is not None:
        problems += _missing(os_tables["en"], os_tables["he"])

    print()
    print("\n".join(problems) if problems else "layouts.py matches the OS.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
