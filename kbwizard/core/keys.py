"""Physical key identities shared by every layout table.

Tables are keyed by Set-1 scan code, the value Windows uses in
``MapVirtualKeyEx`` and ``ToUnicodeEx``, so converting between layouts is
a lookup in one table and a read from the other.
"""

from __future__ import annotations

from enum import IntEnum


class ScanCode(IntEnum):
    """Set-1 scan codes of the keys that differ between layouts, named by US-QWERTY legend."""

    # Number row: only 9 and 0, whose shifted parentheses differ.
    GRAVE = 41
    DIGIT9 = 10
    DIGIT0 = 11

    # Top letter row.
    Q = 16
    W = 17
    E = 18
    R = 19
    T = 20
    Y = 21
    U = 22
    I = 23
    O = 24
    P = 25
    LBRACKET = 26
    RBRACKET = 27

    # Home row.
    A = 30
    S = 31
    D = 32
    F = 33
    G = 34
    H = 35
    J = 36
    K = 37
    L = 38
    SEMICOLON = 39
    APOSTROPHE = 40

    # Bottom row.
    Z = 44
    X = 45
    C = 46
    V = 47
    B = 48
    N = 49
    M = 50
    COMMA = 51
    PERIOD = 52
    SLASH = 53


# (scan code, Shift held). Shift is part of the identity because some
# shifted symbols differ per layout (Hebrew mirrors the brackets).
KeyStroke = tuple[ScanCode, bool]
