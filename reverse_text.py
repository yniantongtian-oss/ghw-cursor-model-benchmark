"""Reverse text by Unicode extended grapheme clusters.

``s[::-1]`` reverses code points. Real text often stores one user-perceived
character as several code points: a base letter plus combining accents, an
emoji plus a skin-tone modifier, a ZWJ family sequence, a flag of two regional
indicators, or a keycap. Reversing those pieces pulls the character apart.

``reverse_text`` reverses extended grapheme clusters, the cursor-movement units
defined by Unicode Standard Annex #29 (Unicode 18.0.0). Code points inside a
cluster stay in their original order, so a decomposed accent stays decomposed.
The reversal follows logical storage order.
"""

import bisect

__all__ = ["reverse_text"]

# Grapheme_Cluster_Break values. Code points omitted from the tables are Other.
_OTHER = 0
_CR = 1
_LF = 2
_CONTROL = 3
_EXTEND = 4
_ZWJ = 5
_REGIONAL_INDICATOR = 6
_PREPEND = 7
_SPACING_MARK = 8
_HANGUL_L = 9
_HANGUL_V = 10
_HANGUL_T = 11
_HANGUL_LV = 12
_HANGUL_LVT = 13

# Indic_Conjunct_Break values. Omitted code points are None.
_INCB_NONE = 0
_INCB_EXTEND = 1
_INCB_LINKER = 2
_INCB_CONSONANT = 3

_BREAK_CONTROL = (_CONTROL, _CR, _LF)


def reverse_text(s: str) -> str:
    """Reverse *s* one extended grapheme cluster at a time.

    A cluster is one user-perceived character: a base with its combining marks,
    an emoji with skin tone or ZWJ joiners, a regional-indicator flag, a Hangul
    syllable, or an Indic conjunct linked by a virama. Clusters are concatenated
    in reverse order. The code points inside each cluster are left as they were,
    including whether a letter is precomposed or decomposed.

    Args:
        s: Text to reverse.

    Returns:
        The grapheme-cluster reversal of *s*. The empty string and any single
        cluster are returned unchanged.

    Raises:
        TypeError: *s* is not a ``str``.

    Examples::

        reverse_text("hello") -> "olleh"
        reverse_text("café") -> "éfac"
        reverse_text("cafe\\u0301") -> "e\\u0301fac"
        reverse_text("a👍🏽b") -> "b👍🏽a"
        reverse_text("你好") -> "好你"
        reverse_text("👨‍👩‍👧‍👦") -> "👨‍👩‍👧‍👦"
    """
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    if len(s) < 2:
        return s
    clusters = _grapheme_clusters(s)
    clusters.reverse()
    return "".join(clusters)


def _grapheme_clusters(s: str) -> list[str]:
    """Split *s* into extended grapheme clusters (UAX #29, Unicode 18.0.0).

    The scan applies the boundary rules in order. State carried from one code
    point to the next remembers only what the rules look behind for:

    * ``extpict_extend``: the current suffix matches
      ``Extended_Pictographic Extend*`` (the left side of GB11, before ZWJ).
    * ``gb11_zwj``: that suffix was just closed by a ZWJ, so a following
      extended pictographic must stay in the same cluster (GB11).
    * ``ri_count``: how many regional indicators end the current suffix.
      GB12/GB13 keep a pair together when the count so far is odd.
    * ``gb9c_ready``: the suffix matches ``InCB=Linker InCB=Extend*``, so a
      following ``InCB=Consonant`` stays in the cluster (GB9c).
    """
    if not s:
        return []
    clusters: list[str] = []
    start = 0
    prev_gcb = _OTHER
    extpict_extend = False
    gb11_zwj = False
    ri_count = 0
    gb9c_ready = False

    for index, char in enumerate(s):
        code_point = ord(char)
        gcb = _grapheme_break(code_point)
        incb = _indic_conjunct_break(code_point)
        extended_pictographic = _is_extended_pictographic(code_point)
        if index and _is_boundary(
            prev_gcb,
            gcb,
            incb,
            extended_pictographic,
            gb11_zwj,
            ri_count,
            gb9c_ready,
        ):
            clusters.append(s[start:index])
            start = index

        prev_gcb = gcb
        if gcb == _ZWJ:
            gb11_zwj = extpict_extend
            extpict_extend = False
        elif gcb == _EXTEND:
            extpict_extend = extpict_extend or extended_pictographic
            gb11_zwj = False
        elif extended_pictographic:
            extpict_extend = True
            gb11_zwj = False
        else:
            extpict_extend = False
            gb11_zwj = False

        ri_count = ri_count + 1 if gcb == _REGIONAL_INDICATOR else 0
        if incb == _INCB_LINKER:
            gb9c_ready = True
        elif incb != _INCB_EXTEND:
            gb9c_ready = False

    clusters.append(s[start:])
    return clusters


def _is_boundary(
    prev_gcb: int,
    gcb: int,
    incb: int,
    extended_pictographic: bool,
    gb11_zwj: bool,
    ri_count: int,
    gb9c_ready: bool,
) -> bool:
    """Return whether UAX #29 places a break between the previous and current code point.

    Rules are listed in the order the standard gives them. The first match wins.
    """
    # GB3: keep CRLF together. GB4/GB5: break around controls otherwise.
    if prev_gcb == _CR and gcb == _LF:
        return False
    if prev_gcb in _BREAK_CONTROL or gcb in _BREAK_CONTROL:
        return True
    # GB6–GB8: Hangul conjoining jamo and composed syllables.
    if prev_gcb == _HANGUL_L and gcb in (_HANGUL_L, _HANGUL_V, _HANGUL_LV, _HANGUL_LVT):
        return False
    if prev_gcb in (_HANGUL_LV, _HANGUL_V) and gcb in (_HANGUL_V, _HANGUL_T):
        return False
    if prev_gcb in (_HANGUL_LVT, _HANGUL_T) and gcb == _HANGUL_T:
        return False
    # GB9 / GB9a / GB9b: extenders, spacing marks, and prepend characters.
    if gcb in (_EXTEND, _ZWJ) or gcb == _SPACING_MARK:
        return False
    if prev_gcb == _PREPEND:
        return False
    # GB9c: virama (and other linkers) plus optional InCB extenders, then a consonant.
    if incb == _INCB_CONSONANT and gb9c_ready:
        return False
    # GB11: emoji ZWJ sequences, including skin tone before the joiner.
    if extended_pictographic and gb11_zwj:
        return False
    # GB12/GB13: flag pairs. An odd count means this indicator completes a pair.
    if prev_gcb == _REGIONAL_INDICATOR and gcb == _REGIONAL_INDICATOR and ri_count & 1:
        return False
    # GB999.
    return True


def _grapheme_break(code_point: int) -> int:
    """Return the Grapheme_Cluster_Break of *code_point*."""
    if 0xAC00 <= code_point <= 0xD7A3:
        # Hangul syllables: U+AC00 is LV, then 27 LVT, repeating.
        if (code_point - 0xAC00) % 28 == 0:
            return _HANGUL_LV
        return _HANGUL_LVT
    return _lookup(code_point, _GCB_STARTS, _GCB_ENDS, _GCB_VALUES, _OTHER)


def _indic_conjunct_break(code_point: int) -> int:
    """Return the Indic_Conjunct_Break of *code_point*."""
    return _lookup(code_point, _INCB_STARTS, _INCB_ENDS, _INCB_VALUES, _INCB_NONE)


def _is_extended_pictographic(code_point: int) -> bool:
    """Return whether *code_point* has Extended_Pictographic=Yes."""
    index = bisect.bisect_right(_EXTPICT_STARTS, code_point) - 1
    return index >= 0 and code_point <= _EXTPICT_ENDS[index]


def _lookup(
    code_point: int,
    starts: tuple[int, ...],
    ends: tuple[int, ...],
    values: tuple[int, ...],
    default: int,
) -> int:
    """Binary-search inclusive ranges sorted by start."""
    index = bisect.bisect_right(starts, code_point) - 1
    if index >= 0 and code_point <= ends[index]:
        return values[index]
    return default


def _columns(
    ranges: tuple[tuple[int, int, int], ...],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Split ``(start, end, value)`` rows into parallel lookup columns."""
    return (
        tuple(start for start, _end, _value in ranges),
        tuple(end for _start, end, _value in ranges),
        tuple(value for _start, _end, value in ranges),
    )


# Tables derived from the Unicode 18.0.0 Character Database:
#   auxiliary/GraphemeBreakProperty.txt
#   emoji/emoji-data.txt (Extended_Pictographic)
#   DerivedCoreProperties.txt (Indic_Conjunct_Break)
# Copyright (c) 2026 Unicode, Inc.
# Unicode and the Unicode Logo are registered trademarks of Unicode, Inc.
# See https://www.unicode.org/terms_of_use.html
# Code points that do not appear here use the default for that property
# (Grapheme_Cluster_Break=Other, Indic_Conjunct_Break=None,
# Extended_Pictographic=No). Hangul syllable types LV and LVT are computed in
# ``_grapheme_break`` for U+AC00..U+D7A3, matching GraphemeBreakProperty.txt.

_GCB_RANGES: tuple[tuple[int, int, int], ...] = (
    (0x0000, 0x0009, _CONTROL),  # Control
    (0x000A, 0x000A, _LF),  # LF
    (0x000B, 0x000C, _CONTROL),  # Control
    (0x000D, 0x000D, _CR),  # CR
    (0x000E, 0x001F, _CONTROL),  # Control
    (0x007F, 0x009F, _CONTROL),  # Control
    (0x00AD, 0x00AD, _CONTROL),  # Control
    (0x0300, 0x036F, _EXTEND),  # Extend
    (0x0483, 0x0489, _EXTEND),  # Extend
    (0x0591, 0x05BD, _EXTEND),  # Extend
    (0x05BF, 0x05BF, _EXTEND),  # Extend
    (0x05C1, 0x05C2, _EXTEND),  # Extend
    (0x05C4, 0x05C5, _EXTEND),  # Extend
    (0x05C7, 0x05C9, _EXTEND),  # Extend
    (0x0600, 0x0605, _PREPEND),  # Prepend
    (0x0610, 0x061A, _EXTEND),  # Extend
    (0x061C, 0x061C, _CONTROL),  # Control
    (0x064B, 0x065F, _EXTEND),  # Extend
    (0x0670, 0x0670, _EXTEND),  # Extend
    (0x06D6, 0x06DC, _EXTEND),  # Extend
    (0x06DD, 0x06DD, _PREPEND),  # Prepend
    (0x06DF, 0x06E4, _EXTEND),  # Extend
    (0x06E7, 0x06E8, _EXTEND),  # Extend
    (0x06EA, 0x06ED, _EXTEND),  # Extend
    (0x070F, 0x070F, _PREPEND),  # Prepend
    (0x0711, 0x0711, _EXTEND),  # Extend
    (0x0730, 0x074A, _EXTEND),  # Extend
    (0x07A6, 0x07B0, _EXTEND),  # Extend
    (0x07EB, 0x07F3, _EXTEND),  # Extend
    (0x07FD, 0x07FD, _EXTEND),  # Extend
    (0x0816, 0x0819, _EXTEND),  # Extend
    (0x081B, 0x0823, _EXTEND),  # Extend
    (0x0825, 0x0827, _EXTEND),  # Extend
    (0x0829, 0x082D, _EXTEND),  # Extend
    (0x0859, 0x085B, _EXTEND),  # Extend
    (0x0890, 0x0891, _PREPEND),  # Prepend
    (0x0897, 0x089F, _EXTEND),  # Extend
    (0x08CA, 0x08E1, _EXTEND),  # Extend
    (0x08E2, 0x08E2, _PREPEND),  # Prepend
    (0x08E3, 0x0902, _EXTEND),  # Extend
    (0x0903, 0x0903, _SPACING_MARK),  # SpacingMark
    (0x093A, 0x093A, _EXTEND),  # Extend
    (0x093B, 0x093B, _SPACING_MARK),  # SpacingMark
    (0x093C, 0x093C, _EXTEND),  # Extend
    (0x093E, 0x0940, _SPACING_MARK),  # SpacingMark
    (0x0941, 0x0948, _EXTEND),  # Extend
    (0x0949, 0x094C, _SPACING_MARK),  # SpacingMark
    (0x094D, 0x094D, _EXTEND),  # Extend
    (0x094E, 0x094F, _SPACING_MARK),  # SpacingMark
    (0x0951, 0x0957, _EXTEND),  # Extend
    (0x0962, 0x0963, _EXTEND),  # Extend
    (0x0981, 0x0981, _EXTEND),  # Extend
    (0x0982, 0x0983, _SPACING_MARK),  # SpacingMark
    (0x09BC, 0x09BC, _EXTEND),  # Extend
    (0x09BE, 0x09BE, _EXTEND),  # Extend
    (0x09BF, 0x09C0, _SPACING_MARK),  # SpacingMark
    (0x09C1, 0x09C4, _EXTEND),  # Extend
    (0x09C7, 0x09C8, _SPACING_MARK),  # SpacingMark
    (0x09CB, 0x09CC, _SPACING_MARK),  # SpacingMark
    (0x09CD, 0x09CD, _EXTEND),  # Extend
    (0x09D7, 0x09D7, _EXTEND),  # Extend
    (0x09E2, 0x09E3, _EXTEND),  # Extend
    (0x09FE, 0x09FE, _EXTEND),  # Extend
    (0x0A01, 0x0A02, _EXTEND),  # Extend
    (0x0A03, 0x0A03, _SPACING_MARK),  # SpacingMark
    (0x0A3C, 0x0A3C, _EXTEND),  # Extend
    (0x0A3E, 0x0A40, _SPACING_MARK),  # SpacingMark
    (0x0A41, 0x0A42, _EXTEND),  # Extend
    (0x0A47, 0x0A48, _EXTEND),  # Extend
    (0x0A4B, 0x0A4D, _EXTEND),  # Extend
    (0x0A51, 0x0A51, _EXTEND),  # Extend
    (0x0A70, 0x0A71, _EXTEND),  # Extend
    (0x0A75, 0x0A75, _EXTEND),  # Extend
    (0x0A81, 0x0A82, _EXTEND),  # Extend
    (0x0A83, 0x0A83, _SPACING_MARK),  # SpacingMark
    (0x0ABC, 0x0ABC, _EXTEND),  # Extend
    (0x0ABE, 0x0AC0, _SPACING_MARK),  # SpacingMark
    (0x0AC1, 0x0AC5, _EXTEND),  # Extend
    (0x0AC7, 0x0AC8, _EXTEND),  # Extend
    (0x0AC9, 0x0AC9, _SPACING_MARK),  # SpacingMark
    (0x0ACB, 0x0ACC, _SPACING_MARK),  # SpacingMark
    (0x0ACD, 0x0ACD, _EXTEND),  # Extend
    (0x0AE2, 0x0AE3, _EXTEND),  # Extend
    (0x0AFA, 0x0AFF, _EXTEND),  # Extend
    (0x0B01, 0x0B01, _EXTEND),  # Extend
    (0x0B02, 0x0B03, _SPACING_MARK),  # SpacingMark
    (0x0B3C, 0x0B3C, _EXTEND),  # Extend
    (0x0B3E, 0x0B3F, _EXTEND),  # Extend
    (0x0B40, 0x0B40, _SPACING_MARK),  # SpacingMark
    (0x0B41, 0x0B44, _EXTEND),  # Extend
    (0x0B47, 0x0B48, _SPACING_MARK),  # SpacingMark
    (0x0B4B, 0x0B4C, _SPACING_MARK),  # SpacingMark
    (0x0B4D, 0x0B4D, _EXTEND),  # Extend
    (0x0B53, 0x0B57, _EXTEND),  # Extend
    (0x0B62, 0x0B63, _EXTEND),  # Extend
    (0x0B82, 0x0B82, _EXTEND),  # Extend
    (0x0BBE, 0x0BBE, _EXTEND),  # Extend
    (0x0BBF, 0x0BBF, _SPACING_MARK),  # SpacingMark
    (0x0BC0, 0x0BC0, _EXTEND),  # Extend
    (0x0BC1, 0x0BC2, _SPACING_MARK),  # SpacingMark
    (0x0BC6, 0x0BC8, _SPACING_MARK),  # SpacingMark
    (0x0BCA, 0x0BCC, _SPACING_MARK),  # SpacingMark
    (0x0BCD, 0x0BCD, _EXTEND),  # Extend
    (0x0BD7, 0x0BD7, _EXTEND),  # Extend
    (0x0C00, 0x0C00, _EXTEND),  # Extend
    (0x0C01, 0x0C03, _SPACING_MARK),  # SpacingMark
    (0x0C04, 0x0C04, _EXTEND),  # Extend
    (0x0C3C, 0x0C3C, _EXTEND),  # Extend
    (0x0C3E, 0x0C40, _EXTEND),  # Extend
    (0x0C41, 0x0C44, _SPACING_MARK),  # SpacingMark
    (0x0C46, 0x0C48, _EXTEND),  # Extend
    (0x0C4A, 0x0C4D, _EXTEND),  # Extend
    (0x0C55, 0x0C56, _EXTEND),  # Extend
    (0x0C62, 0x0C63, _EXTEND),  # Extend
    (0x0C81, 0x0C81, _EXTEND),  # Extend
    (0x0C82, 0x0C83, _SPACING_MARK),  # SpacingMark
    (0x0CBC, 0x0CBC, _EXTEND),  # Extend
    (0x0CBE, 0x0CBE, _SPACING_MARK),  # SpacingMark
    (0x0CBF, 0x0CC0, _EXTEND),  # Extend
    (0x0CC1, 0x0CC1, _SPACING_MARK),  # SpacingMark
    (0x0CC2, 0x0CC2, _EXTEND),  # Extend
    (0x0CC3, 0x0CC4, _SPACING_MARK),  # SpacingMark
    (0x0CC6, 0x0CC8, _EXTEND),  # Extend
    (0x0CCA, 0x0CCD, _EXTEND),  # Extend
    (0x0CD5, 0x0CD6, _EXTEND),  # Extend
    (0x0CE2, 0x0CE3, _EXTEND),  # Extend
    (0x0CF3, 0x0CF3, _SPACING_MARK),  # SpacingMark
    (0x0D00, 0x0D01, _EXTEND),  # Extend
    (0x0D02, 0x0D03, _SPACING_MARK),  # SpacingMark
    (0x0D3B, 0x0D3C, _EXTEND),  # Extend
    (0x0D3E, 0x0D3E, _EXTEND),  # Extend
    (0x0D3F, 0x0D40, _SPACING_MARK),  # SpacingMark
    (0x0D41, 0x0D44, _EXTEND),  # Extend
    (0x0D46, 0x0D48, _SPACING_MARK),  # SpacingMark
    (0x0D4A, 0x0D4C, _SPACING_MARK),  # SpacingMark
    (0x0D4D, 0x0D4D, _EXTEND),  # Extend
    (0x0D4E, 0x0D4E, _PREPEND),  # Prepend
    (0x0D57, 0x0D57, _EXTEND),  # Extend
    (0x0D62, 0x0D63, _EXTEND),  # Extend
    (0x0D81, 0x0D81, _EXTEND),  # Extend
    (0x0D82, 0x0D83, _SPACING_MARK),  # SpacingMark
    (0x0DCA, 0x0DCA, _EXTEND),  # Extend
    (0x0DCF, 0x0DCF, _EXTEND),  # Extend
    (0x0DD0, 0x0DD1, _SPACING_MARK),  # SpacingMark
    (0x0DD2, 0x0DD4, _EXTEND),  # Extend
    (0x0DD6, 0x0DD6, _EXTEND),  # Extend
    (0x0DD8, 0x0DDE, _SPACING_MARK),  # SpacingMark
    (0x0DDF, 0x0DDF, _EXTEND),  # Extend
    (0x0DF2, 0x0DF3, _SPACING_MARK),  # SpacingMark
    (0x0E31, 0x0E31, _EXTEND),  # Extend
    (0x0E33, 0x0E33, _SPACING_MARK),  # SpacingMark
    (0x0E34, 0x0E3A, _EXTEND),  # Extend
    (0x0E47, 0x0E4E, _EXTEND),  # Extend
    (0x0EB1, 0x0EB1, _EXTEND),  # Extend
    (0x0EB3, 0x0EB3, _SPACING_MARK),  # SpacingMark
    (0x0EB4, 0x0EBC, _EXTEND),  # Extend
    (0x0EC8, 0x0ECE, _EXTEND),  # Extend
    (0x0F18, 0x0F19, _EXTEND),  # Extend
    (0x0F35, 0x0F35, _EXTEND),  # Extend
    (0x0F37, 0x0F37, _EXTEND),  # Extend
    (0x0F39, 0x0F39, _EXTEND),  # Extend
    (0x0F3E, 0x0F3F, _SPACING_MARK),  # SpacingMark
    (0x0F71, 0x0F7E, _EXTEND),  # Extend
    (0x0F7F, 0x0F7F, _SPACING_MARK),  # SpacingMark
    (0x0F80, 0x0F84, _EXTEND),  # Extend
    (0x0F86, 0x0F87, _EXTEND),  # Extend
    (0x0F8D, 0x0F97, _EXTEND),  # Extend
    (0x0F99, 0x0FBC, _EXTEND),  # Extend
    (0x0FC6, 0x0FC6, _EXTEND),  # Extend
    (0x102D, 0x1030, _EXTEND),  # Extend
    (0x1031, 0x1031, _SPACING_MARK),  # SpacingMark
    (0x1032, 0x1037, _EXTEND),  # Extend
    (0x1039, 0x103A, _EXTEND),  # Extend
    (0x103B, 0x103C, _SPACING_MARK),  # SpacingMark
    (0x103D, 0x103E, _EXTEND),  # Extend
    (0x1056, 0x1057, _SPACING_MARK),  # SpacingMark
    (0x1058, 0x1059, _EXTEND),  # Extend
    (0x105E, 0x1060, _EXTEND),  # Extend
    (0x1071, 0x1074, _EXTEND),  # Extend
    (0x1082, 0x1082, _EXTEND),  # Extend
    (0x1084, 0x1084, _SPACING_MARK),  # SpacingMark
    (0x1085, 0x1086, _EXTEND),  # Extend
    (0x108D, 0x108D, _EXTEND),  # Extend
    (0x109D, 0x109D, _EXTEND),  # Extend
    (0x1100, 0x115F, _HANGUL_L),  # L
    (0x1160, 0x11A7, _HANGUL_V),  # V
    (0x11A8, 0x11FF, _HANGUL_T),  # T
    (0x135D, 0x135F, _EXTEND),  # Extend
    (0x1712, 0x1715, _EXTEND),  # Extend
    (0x1732, 0x1734, _EXTEND),  # Extend
    (0x1752, 0x1753, _EXTEND),  # Extend
    (0x1772, 0x1773, _EXTEND),  # Extend
    (0x17B4, 0x17B5, _EXTEND),  # Extend
    (0x17B6, 0x17B6, _SPACING_MARK),  # SpacingMark
    (0x17B7, 0x17BD, _EXTEND),  # Extend
    (0x17BE, 0x17C5, _SPACING_MARK),  # SpacingMark
    (0x17C6, 0x17C6, _EXTEND),  # Extend
    (0x17C7, 0x17C8, _SPACING_MARK),  # SpacingMark
    (0x17C9, 0x17D3, _EXTEND),  # Extend
    (0x17DD, 0x17DD, _EXTEND),  # Extend
    (0x180B, 0x180D, _EXTEND),  # Extend
    (0x180E, 0x180E, _CONTROL),  # Control
    (0x180F, 0x180F, _EXTEND),  # Extend
    (0x1885, 0x1886, _EXTEND),  # Extend
    (0x18A9, 0x18A9, _EXTEND),  # Extend
    (0x1920, 0x1922, _EXTEND),  # Extend
    (0x1923, 0x1926, _SPACING_MARK),  # SpacingMark
    (0x1927, 0x1928, _EXTEND),  # Extend
    (0x1929, 0x192B, _SPACING_MARK),  # SpacingMark
    (0x1930, 0x1931, _SPACING_MARK),  # SpacingMark
    (0x1932, 0x1932, _EXTEND),  # Extend
    (0x1933, 0x1938, _SPACING_MARK),  # SpacingMark
    (0x1939, 0x193B, _EXTEND),  # Extend
    (0x1A17, 0x1A18, _EXTEND),  # Extend
    (0x1A19, 0x1A1A, _SPACING_MARK),  # SpacingMark
    (0x1A1B, 0x1A1B, _EXTEND),  # Extend
    (0x1A55, 0x1A55, _SPACING_MARK),  # SpacingMark
    (0x1A56, 0x1A56, _EXTEND),  # Extend
    (0x1A57, 0x1A57, _SPACING_MARK),  # SpacingMark
    (0x1A58, 0x1A5E, _EXTEND),  # Extend
    (0x1A60, 0x1A60, _EXTEND),  # Extend
    (0x1A62, 0x1A62, _EXTEND),  # Extend
    (0x1A65, 0x1A6C, _EXTEND),  # Extend
    (0x1A6D, 0x1A72, _SPACING_MARK),  # SpacingMark
    (0x1A73, 0x1A7C, _EXTEND),  # Extend
    (0x1A7F, 0x1A7F, _EXTEND),  # Extend
    (0x1AB0, 0x1AF0, _EXTEND),  # Extend
    (0x1B00, 0x1B03, _EXTEND),  # Extend
    (0x1B04, 0x1B04, _SPACING_MARK),  # SpacingMark
    (0x1B34, 0x1B3D, _EXTEND),  # Extend
    (0x1B3E, 0x1B41, _SPACING_MARK),  # SpacingMark
    (0x1B42, 0x1B44, _EXTEND),  # Extend
    (0x1B6B, 0x1B73, _EXTEND),  # Extend
    (0x1B80, 0x1B81, _EXTEND),  # Extend
    (0x1B82, 0x1B82, _SPACING_MARK),  # SpacingMark
    (0x1BA1, 0x1BA1, _SPACING_MARK),  # SpacingMark
    (0x1BA2, 0x1BA5, _EXTEND),  # Extend
    (0x1BA6, 0x1BA7, _SPACING_MARK),  # SpacingMark
    (0x1BA8, 0x1BAD, _EXTEND),  # Extend
    (0x1BE6, 0x1BE6, _EXTEND),  # Extend
    (0x1BE7, 0x1BE7, _SPACING_MARK),  # SpacingMark
    (0x1BE8, 0x1BE9, _EXTEND),  # Extend
    (0x1BEA, 0x1BEC, _SPACING_MARK),  # SpacingMark
    (0x1BED, 0x1BED, _EXTEND),  # Extend
    (0x1BEE, 0x1BEE, _SPACING_MARK),  # SpacingMark
    (0x1BEF, 0x1BF3, _EXTEND),  # Extend
    (0x1C24, 0x1C2B, _SPACING_MARK),  # SpacingMark
    (0x1C2C, 0x1C33, _EXTEND),  # Extend
    (0x1C34, 0x1C35, _SPACING_MARK),  # SpacingMark
    (0x1C36, 0x1C37, _EXTEND),  # Extend
    (0x1CD0, 0x1CD2, _EXTEND),  # Extend
    (0x1CD4, 0x1CE0, _EXTEND),  # Extend
    (0x1CE1, 0x1CE1, _SPACING_MARK),  # SpacingMark
    (0x1CE2, 0x1CE8, _EXTEND),  # Extend
    (0x1CED, 0x1CED, _EXTEND),  # Extend
    (0x1CF4, 0x1CF4, _EXTEND),  # Extend
    (0x1CF7, 0x1CF7, _SPACING_MARK),  # SpacingMark
    (0x1CF8, 0x1CF9, _EXTEND),  # Extend
    (0x1DC0, 0x1DFF, _EXTEND),  # Extend
    (0x200B, 0x200B, _CONTROL),  # Control
    (0x200C, 0x200C, _EXTEND),  # Extend
    (0x200D, 0x200D, _ZWJ),  # ZWJ
    (0x200E, 0x200F, _CONTROL),  # Control
    (0x2028, 0x202E, _CONTROL),  # Control
    (0x2060, 0x206F, _CONTROL),  # Control
    (0x20D0, 0x20F0, _EXTEND),  # Extend
    (0x2CEF, 0x2CF1, _EXTEND),  # Extend
    (0x2D7F, 0x2D7F, _EXTEND),  # Extend
    (0x2DE0, 0x2DFF, _EXTEND),  # Extend
    (0x302A, 0x302F, _EXTEND),  # Extend
    (0x3099, 0x309A, _EXTEND),  # Extend
    (0xA66F, 0xA672, _EXTEND),  # Extend
    (0xA674, 0xA67D, _EXTEND),  # Extend
    (0xA69E, 0xA69F, _EXTEND),  # Extend
    (0xA6F0, 0xA6F1, _EXTEND),  # Extend
    (0xA802, 0xA802, _EXTEND),  # Extend
    (0xA806, 0xA806, _EXTEND),  # Extend
    (0xA80B, 0xA80B, _EXTEND),  # Extend
    (0xA823, 0xA824, _SPACING_MARK),  # SpacingMark
    (0xA825, 0xA826, _EXTEND),  # Extend
    (0xA827, 0xA827, _SPACING_MARK),  # SpacingMark
    (0xA82C, 0xA82C, _EXTEND),  # Extend
    (0xA880, 0xA881, _SPACING_MARK),  # SpacingMark
    (0xA8B4, 0xA8C3, _SPACING_MARK),  # SpacingMark
    (0xA8C4, 0xA8C5, _EXTEND),  # Extend
    (0xA8E0, 0xA8F1, _EXTEND),  # Extend
    (0xA8FF, 0xA8FF, _EXTEND),  # Extend
    (0xA926, 0xA92D, _EXTEND),  # Extend
    (0xA947, 0xA951, _EXTEND),  # Extend
    (0xA952, 0xA952, _SPACING_MARK),  # SpacingMark
    (0xA953, 0xA953, _EXTEND),  # Extend
    (0xA960, 0xA97C, _HANGUL_L),  # L
    (0xA980, 0xA982, _EXTEND),  # Extend
    (0xA983, 0xA983, _SPACING_MARK),  # SpacingMark
    (0xA9B3, 0xA9B3, _EXTEND),  # Extend
    (0xA9B4, 0xA9B5, _SPACING_MARK),  # SpacingMark
    (0xA9B6, 0xA9B9, _EXTEND),  # Extend
    (0xA9BA, 0xA9BB, _SPACING_MARK),  # SpacingMark
    (0xA9BC, 0xA9BD, _EXTEND),  # Extend
    (0xA9BE, 0xA9BF, _SPACING_MARK),  # SpacingMark
    (0xA9C0, 0xA9C0, _EXTEND),  # Extend
    (0xA9E5, 0xA9E5, _EXTEND),  # Extend
    (0xAA29, 0xAA2E, _EXTEND),  # Extend
    (0xAA2F, 0xAA30, _SPACING_MARK),  # SpacingMark
    (0xAA31, 0xAA32, _EXTEND),  # Extend
    (0xAA33, 0xAA34, _SPACING_MARK),  # SpacingMark
    (0xAA35, 0xAA36, _EXTEND),  # Extend
    (0xAA43, 0xAA43, _EXTEND),  # Extend
    (0xAA4C, 0xAA4C, _EXTEND),  # Extend
    (0xAA4D, 0xAA4D, _SPACING_MARK),  # SpacingMark
    (0xAA7C, 0xAA7C, _EXTEND),  # Extend
    (0xAAB0, 0xAAB0, _EXTEND),  # Extend
    (0xAAB2, 0xAAB4, _EXTEND),  # Extend
    (0xAAB7, 0xAAB8, _EXTEND),  # Extend
    (0xAABE, 0xAABF, _EXTEND),  # Extend
    (0xAAC1, 0xAAC1, _EXTEND),  # Extend
    (0xAAEB, 0xAAEB, _SPACING_MARK),  # SpacingMark
    (0xAAEC, 0xAAED, _EXTEND),  # Extend
    (0xAAEE, 0xAAEF, _SPACING_MARK),  # SpacingMark
    (0xAAF5, 0xAAF5, _SPACING_MARK),  # SpacingMark
    (0xAAF6, 0xAAF6, _EXTEND),  # Extend
    (0xABE3, 0xABE4, _SPACING_MARK),  # SpacingMark
    (0xABE5, 0xABE5, _EXTEND),  # Extend
    (0xABE6, 0xABE7, _SPACING_MARK),  # SpacingMark
    (0xABE8, 0xABE8, _EXTEND),  # Extend
    (0xABE9, 0xABEA, _SPACING_MARK),  # SpacingMark
    (0xABEC, 0xABEC, _SPACING_MARK),  # SpacingMark
    (0xABED, 0xABED, _EXTEND),  # Extend
    (0xD7B0, 0xD7C6, _HANGUL_V),  # V
    (0xD7CB, 0xD7FB, _HANGUL_T),  # T
    (0xFB1E, 0xFB1E, _EXTEND),  # Extend
    (0xFE00, 0xFE0F, _EXTEND),  # Extend
    (0xFE20, 0xFE2F, _EXTEND),  # Extend
    (0xFEFF, 0xFEFF, _CONTROL),  # Control
    (0xFF9E, 0xFF9F, _EXTEND),  # Extend
    (0xFFF0, 0xFFFB, _CONTROL),  # Control
    (0x101FD, 0x101FD, _EXTEND),  # Extend
    (0x102E0, 0x102E0, _EXTEND),  # Extend
    (0x10376, 0x1037A, _EXTEND),  # Extend
    (0x10A01, 0x10A03, _EXTEND),  # Extend
    (0x10A05, 0x10A06, _EXTEND),  # Extend
    (0x10A0C, 0x10A0F, _EXTEND),  # Extend
    (0x10A38, 0x10A3A, _EXTEND),  # Extend
    (0x10A3F, 0x10A3F, _EXTEND),  # Extend
    (0x10AE5, 0x10AE6, _EXTEND),  # Extend
    (0x10D24, 0x10D27, _EXTEND),  # Extend
    (0x10D69, 0x10D6D, _EXTEND),  # Extend
    (0x10EAB, 0x10EAC, _EXTEND),  # Extend
    (0x10ECB, 0x10ECF, _EXTEND),  # Extend
    (0x10EF0, 0x10EFF, _EXTEND),  # Extend
    (0x10F46, 0x10F50, _EXTEND),  # Extend
    (0x10F82, 0x10F85, _EXTEND),  # Extend
    (0x11000, 0x11000, _SPACING_MARK),  # SpacingMark
    (0x11001, 0x11001, _EXTEND),  # Extend
    (0x11002, 0x11002, _SPACING_MARK),  # SpacingMark
    (0x11038, 0x11046, _EXTEND),  # Extend
    (0x11070, 0x11070, _EXTEND),  # Extend
    (0x11073, 0x11074, _EXTEND),  # Extend
    (0x1107F, 0x11081, _EXTEND),  # Extend
    (0x11082, 0x11082, _SPACING_MARK),  # SpacingMark
    (0x110B0, 0x110B2, _SPACING_MARK),  # SpacingMark
    (0x110B3, 0x110B6, _EXTEND),  # Extend
    (0x110B7, 0x110B8, _SPACING_MARK),  # SpacingMark
    (0x110B9, 0x110BA, _EXTEND),  # Extend
    (0x110BD, 0x110BD, _PREPEND),  # Prepend
    (0x110C2, 0x110C2, _EXTEND),  # Extend
    (0x110CD, 0x110CD, _PREPEND),  # Prepend
    (0x11100, 0x11102, _EXTEND),  # Extend
    (0x11127, 0x1112B, _EXTEND),  # Extend
    (0x1112C, 0x1112C, _SPACING_MARK),  # SpacingMark
    (0x1112D, 0x11134, _EXTEND),  # Extend
    (0x11145, 0x11146, _SPACING_MARK),  # SpacingMark
    (0x11173, 0x11173, _EXTEND),  # Extend
    (0x11180, 0x11181, _EXTEND),  # Extend
    (0x11182, 0x11182, _SPACING_MARK),  # SpacingMark
    (0x111B3, 0x111B5, _SPACING_MARK),  # SpacingMark
    (0x111B6, 0x111BE, _EXTEND),  # Extend
    (0x111BF, 0x111BF, _SPACING_MARK),  # SpacingMark
    (0x111C0, 0x111C0, _EXTEND),  # Extend
    (0x111C2, 0x111C3, _PREPEND),  # Prepend
    (0x111C9, 0x111CC, _EXTEND),  # Extend
    (0x111CE, 0x111CE, _SPACING_MARK),  # SpacingMark
    (0x111CF, 0x111CF, _EXTEND),  # Extend
    (0x1122C, 0x1122E, _SPACING_MARK),  # SpacingMark
    (0x1122F, 0x11231, _EXTEND),  # Extend
    (0x11232, 0x11233, _SPACING_MARK),  # SpacingMark
    (0x11234, 0x11237, _EXTEND),  # Extend
    (0x1123E, 0x1123E, _EXTEND),  # Extend
    (0x11241, 0x11241, _EXTEND),  # Extend
    (0x112DF, 0x112DF, _EXTEND),  # Extend
    (0x112E0, 0x112E2, _SPACING_MARK),  # SpacingMark
    (0x112E3, 0x112EA, _EXTEND),  # Extend
    (0x11300, 0x11301, _EXTEND),  # Extend
    (0x11302, 0x11303, _SPACING_MARK),  # SpacingMark
    (0x1133B, 0x1133C, _EXTEND),  # Extend
    (0x1133E, 0x1133E, _EXTEND),  # Extend
    (0x1133F, 0x1133F, _SPACING_MARK),  # SpacingMark
    (0x11340, 0x11340, _EXTEND),  # Extend
    (0x11341, 0x11344, _SPACING_MARK),  # SpacingMark
    (0x11347, 0x11348, _SPACING_MARK),  # SpacingMark
    (0x1134B, 0x1134C, _SPACING_MARK),  # SpacingMark
    (0x1134D, 0x1134D, _EXTEND),  # Extend
    (0x11357, 0x11357, _EXTEND),  # Extend
    (0x11362, 0x11363, _SPACING_MARK),  # SpacingMark
    (0x11366, 0x1136C, _EXTEND),  # Extend
    (0x11370, 0x11374, _EXTEND),  # Extend
    (0x113B8, 0x113B8, _EXTEND),  # Extend
    (0x113B9, 0x113BA, _SPACING_MARK),  # SpacingMark
    (0x113BB, 0x113C0, _EXTEND),  # Extend
    (0x113C2, 0x113C2, _EXTEND),  # Extend
    (0x113C5, 0x113C5, _EXTEND),  # Extend
    (0x113C7, 0x113C9, _EXTEND),  # Extend
    (0x113CA, 0x113CA, _SPACING_MARK),  # SpacingMark
    (0x113CC, 0x113CD, _SPACING_MARK),  # SpacingMark
    (0x113CE, 0x113D0, _EXTEND),  # Extend
    (0x113D1, 0x113D1, _PREPEND),  # Prepend
    (0x113D2, 0x113D2, _EXTEND),  # Extend
    (0x113E1, 0x113E2, _EXTEND),  # Extend
    (0x11435, 0x11437, _SPACING_MARK),  # SpacingMark
    (0x11438, 0x1143F, _EXTEND),  # Extend
    (0x11440, 0x11441, _SPACING_MARK),  # SpacingMark
    (0x11442, 0x11444, _EXTEND),  # Extend
    (0x11445, 0x11445, _SPACING_MARK),  # SpacingMark
    (0x11446, 0x11446, _EXTEND),  # Extend
    (0x1145E, 0x1145E, _EXTEND),  # Extend
    (0x114B0, 0x114B0, _EXTEND),  # Extend
    (0x114B1, 0x114B2, _SPACING_MARK),  # SpacingMark
    (0x114B3, 0x114B8, _EXTEND),  # Extend
    (0x114B9, 0x114B9, _SPACING_MARK),  # SpacingMark
    (0x114BA, 0x114BA, _EXTEND),  # Extend
    (0x114BB, 0x114BC, _SPACING_MARK),  # SpacingMark
    (0x114BD, 0x114BD, _EXTEND),  # Extend
    (0x114BE, 0x114BE, _SPACING_MARK),  # SpacingMark
    (0x114BF, 0x114C0, _EXTEND),  # Extend
    (0x114C1, 0x114C1, _SPACING_MARK),  # SpacingMark
    (0x114C2, 0x114C3, _EXTEND),  # Extend
    (0x115AF, 0x115AF, _EXTEND),  # Extend
    (0x115B0, 0x115B1, _SPACING_MARK),  # SpacingMark
    (0x115B2, 0x115B5, _EXTEND),  # Extend
    (0x115B8, 0x115BB, _SPACING_MARK),  # SpacingMark
    (0x115BC, 0x115BD, _EXTEND),  # Extend
    (0x115BE, 0x115BE, _SPACING_MARK),  # SpacingMark
    (0x115BF, 0x115C0, _EXTEND),  # Extend
    (0x115DC, 0x115DD, _EXTEND),  # Extend
    (0x11630, 0x11632, _SPACING_MARK),  # SpacingMark
    (0x11633, 0x1163A, _EXTEND),  # Extend
    (0x1163B, 0x1163C, _SPACING_MARK),  # SpacingMark
    (0x1163D, 0x1163D, _EXTEND),  # Extend
    (0x1163E, 0x1163E, _SPACING_MARK),  # SpacingMark
    (0x1163F, 0x11640, _EXTEND),  # Extend
    (0x116AB, 0x116AB, _EXTEND),  # Extend
    (0x116AC, 0x116AC, _SPACING_MARK),  # SpacingMark
    (0x116AD, 0x116AD, _EXTEND),  # Extend
    (0x116AE, 0x116AF, _SPACING_MARK),  # SpacingMark
    (0x116B0, 0x116B7, _EXTEND),  # Extend
    (0x1171D, 0x1171D, _EXTEND),  # Extend
    (0x1171E, 0x1171E, _SPACING_MARK),  # SpacingMark
    (0x1171F, 0x1171F, _EXTEND),  # Extend
    (0x11722, 0x11725, _EXTEND),  # Extend
    (0x11726, 0x11726, _SPACING_MARK),  # SpacingMark
    (0x11727, 0x1172B, _EXTEND),  # Extend
    (0x1182C, 0x1182E, _SPACING_MARK),  # SpacingMark
    (0x1182F, 0x11837, _EXTEND),  # Extend
    (0x11838, 0x11838, _SPACING_MARK),  # SpacingMark
    (0x11839, 0x1183A, _EXTEND),  # Extend
    (0x11930, 0x11930, _EXTEND),  # Extend
    (0x11931, 0x11935, _SPACING_MARK),  # SpacingMark
    (0x11937, 0x11938, _SPACING_MARK),  # SpacingMark
    (0x1193B, 0x1193E, _EXTEND),  # Extend
    (0x1193F, 0x1193F, _PREPEND),  # Prepend
    (0x11940, 0x11940, _SPACING_MARK),  # SpacingMark
    (0x11941, 0x11941, _PREPEND),  # Prepend
    (0x11942, 0x11942, _SPACING_MARK),  # SpacingMark
    (0x11943, 0x11943, _EXTEND),  # Extend
    (0x119D1, 0x119D3, _SPACING_MARK),  # SpacingMark
    (0x119D4, 0x119D7, _EXTEND),  # Extend
    (0x119DA, 0x119DB, _EXTEND),  # Extend
    (0x119DC, 0x119DF, _SPACING_MARK),  # SpacingMark
    (0x119E0, 0x119E0, _EXTEND),  # Extend
    (0x119E4, 0x119E4, _SPACING_MARK),  # SpacingMark
    (0x11A01, 0x11A0A, _EXTEND),  # Extend
    (0x11A33, 0x11A38, _EXTEND),  # Extend
    (0x11A39, 0x11A39, _SPACING_MARK),  # SpacingMark
    (0x11A3B, 0x11A3E, _EXTEND),  # Extend
    (0x11A47, 0x11A47, _EXTEND),  # Extend
    (0x11A51, 0x11A56, _EXTEND),  # Extend
    (0x11A57, 0x11A58, _SPACING_MARK),  # SpacingMark
    (0x11A59, 0x11A5B, _EXTEND),  # Extend
    (0x11A84, 0x11A89, _PREPEND),  # Prepend
    (0x11A8A, 0x11A96, _EXTEND),  # Extend
    (0x11A97, 0x11A97, _SPACING_MARK),  # SpacingMark
    (0x11A98, 0x11A99, _EXTEND),  # Extend
    (0x11B60, 0x11B60, _EXTEND),  # Extend
    (0x11B61, 0x11B61, _SPACING_MARK),  # SpacingMark
    (0x11B62, 0x11B64, _EXTEND),  # Extend
    (0x11B65, 0x11B65, _SPACING_MARK),  # SpacingMark
    (0x11B66, 0x11B66, _EXTEND),  # Extend
    (0x11B67, 0x11B67, _SPACING_MARK),  # SpacingMark
    (0x11C2F, 0x11C2F, _SPACING_MARK),  # SpacingMark
    (0x11C30, 0x11C36, _EXTEND),  # Extend
    (0x11C38, 0x11C3D, _EXTEND),  # Extend
    (0x11C3E, 0x11C3E, _SPACING_MARK),  # SpacingMark
    (0x11C3F, 0x11C3F, _EXTEND),  # Extend
    (0x11C92, 0x11CA7, _EXTEND),  # Extend
    (0x11CA9, 0x11CA9, _SPACING_MARK),  # SpacingMark
    (0x11CAA, 0x11CB0, _EXTEND),  # Extend
    (0x11CB1, 0x11CB1, _SPACING_MARK),  # SpacingMark
    (0x11CB2, 0x11CB3, _EXTEND),  # Extend
    (0x11CB4, 0x11CB4, _SPACING_MARK),  # SpacingMark
    (0x11CB5, 0x11CB6, _EXTEND),  # Extend
    (0x11D31, 0x11D36, _EXTEND),  # Extend
    (0x11D3A, 0x11D3A, _EXTEND),  # Extend
    (0x11D3C, 0x11D3D, _EXTEND),  # Extend
    (0x11D3F, 0x11D45, _EXTEND),  # Extend
    (0x11D46, 0x11D46, _PREPEND),  # Prepend
    (0x11D47, 0x11D47, _EXTEND),  # Extend
    (0x11D8A, 0x11D8E, _SPACING_MARK),  # SpacingMark
    (0x11D90, 0x11D91, _EXTEND),  # Extend
    (0x11D93, 0x11D94, _SPACING_MARK),  # SpacingMark
    (0x11D95, 0x11D95, _EXTEND),  # Extend
    (0x11D96, 0x11D96, _SPACING_MARK),  # SpacingMark
    (0x11D97, 0x11D97, _EXTEND),  # Extend
    (0x11DF0, 0x11DF0, _EXTEND),  # Extend
    (0x11EF3, 0x11EF4, _EXTEND),  # Extend
    (0x11EF5, 0x11EF6, _SPACING_MARK),  # SpacingMark
    (0x11F00, 0x11F01, _EXTEND),  # Extend
    (0x11F02, 0x11F02, _PREPEND),  # Prepend
    (0x11F03, 0x11F03, _SPACING_MARK),  # SpacingMark
    (0x11F34, 0x11F35, _SPACING_MARK),  # SpacingMark
    (0x11F36, 0x11F3A, _EXTEND),  # Extend
    (0x11F3E, 0x11F3F, _SPACING_MARK),  # SpacingMark
    (0x11F40, 0x11F42, _EXTEND),  # Extend
    (0x11F5A, 0x11F5A, _EXTEND),  # Extend
    (0x13430, 0x1343F, _CONTROL),  # Control
    (0x13440, 0x13440, _EXTEND),  # Extend
    (0x13447, 0x13455, _EXTEND),  # Extend
    (0x1611E, 0x16129, _EXTEND),  # Extend
    (0x1612A, 0x1612C, _SPACING_MARK),  # SpacingMark
    (0x1612D, 0x1612F, _EXTEND),  # Extend
    (0x16AF0, 0x16AF4, _EXTEND),  # Extend
    (0x16B30, 0x16B36, _EXTEND),  # Extend
    (0x16D63, 0x16D63, _HANGUL_V),  # V
    (0x16D67, 0x16D6A, _HANGUL_V),  # V
    (0x16F4F, 0x16F4F, _EXTEND),  # Extend
    (0x16F51, 0x16F87, _SPACING_MARK),  # SpacingMark
    (0x16F8F, 0x16F92, _EXTEND),  # Extend
    (0x16FE4, 0x16FE4, _EXTEND),  # Extend
    (0x16FF0, 0x16FF1, _EXTEND),  # Extend
    (0x1BC9D, 0x1BC9E, _EXTEND),  # Extend
    (0x1BCA0, 0x1BCA3, _CONTROL),  # Control
    (0x1CF00, 0x1CF2D, _EXTEND),  # Extend
    (0x1CF30, 0x1CF46, _EXTEND),  # Extend
    (0x1D127, 0x1D128, _EXTEND),  # Extend
    (0x1D165, 0x1D169, _EXTEND),  # Extend
    (0x1D16D, 0x1D172, _EXTEND),  # Extend
    (0x1D173, 0x1D17A, _CONTROL),  # Control
    (0x1D17B, 0x1D182, _EXTEND),  # Extend
    (0x1D185, 0x1D18B, _EXTEND),  # Extend
    (0x1D1AA, 0x1D1AD, _EXTEND),  # Extend
    (0x1D242, 0x1D244, _EXTEND),  # Extend
    (0x1D250, 0x1D252, _EXTEND),  # Extend
    (0x1D25B, 0x1D25C, _EXTEND),  # Extend
    (0x1D25F, 0x1D25F, _EXTEND),  # Extend
    (0x1D280, 0x1D281, _EXTEND),  # Extend
    (0x1DA00, 0x1DA36, _EXTEND),  # Extend
    (0x1DA3B, 0x1DA6C, _EXTEND),  # Extend
    (0x1DA75, 0x1DA75, _EXTEND),  # Extend
    (0x1DA84, 0x1DA84, _EXTEND),  # Extend
    (0x1DA9B, 0x1DA9F, _EXTEND),  # Extend
    (0x1DAA1, 0x1DAAF, _EXTEND),  # Extend
    (0x1E000, 0x1E006, _EXTEND),  # Extend
    (0x1E008, 0x1E018, _EXTEND),  # Extend
    (0x1E01B, 0x1E021, _EXTEND),  # Extend
    (0x1E023, 0x1E024, _EXTEND),  # Extend
    (0x1E026, 0x1E02A, _EXTEND),  # Extend
    (0x1E08F, 0x1E08F, _EXTEND),  # Extend
    (0x1E130, 0x1E136, _EXTEND),  # Extend
    (0x1E2AE, 0x1E2AE, _EXTEND),  # Extend
    (0x1E2EC, 0x1E2EF, _EXTEND),  # Extend
    (0x1E4EC, 0x1E4EF, _EXTEND),  # Extend
    (0x1E5EE, 0x1E5EF, _EXTEND),  # Extend
    (0x1E6E3, 0x1E6E3, _EXTEND),  # Extend
    (0x1E6E6, 0x1E6E6, _EXTEND),  # Extend
    (0x1E6EE, 0x1E6EF, _EXTEND),  # Extend
    (0x1E6F5, 0x1E6F5, _EXTEND),  # Extend
    (0x1E8D0, 0x1E8D6, _EXTEND),  # Extend
    (0x1E944, 0x1E94A, _EXTEND),  # Extend
    (0x1F1E6, 0x1F1FF, _REGIONAL_INDICATOR),  # Regional_Indicator
    (0x1F3FB, 0x1F3FF, _EXTEND),  # Extend
    (0xE0000, 0xE001F, _CONTROL),  # Control
    (0xE0020, 0xE007F, _EXTEND),  # Extend
    (0xE0080, 0xE00FF, _CONTROL),  # Control
    (0xE0100, 0xE01EF, _EXTEND),  # Extend
    (0xE01F0, 0xE0FFF, _CONTROL),  # Control
)
_INCB_RANGES: tuple[tuple[int, int, int], ...] = (
    (0x0300, 0x036F, _INCB_EXTEND),  # InCB=Extend
    (0x0483, 0x0489, _INCB_EXTEND),  # InCB=Extend
    (0x0591, 0x05BD, _INCB_EXTEND),  # InCB=Extend
    (0x05BF, 0x05BF, _INCB_EXTEND),  # InCB=Extend
    (0x05C1, 0x05C2, _INCB_EXTEND),  # InCB=Extend
    (0x05C4, 0x05C5, _INCB_EXTEND),  # InCB=Extend
    (0x05C7, 0x05C9, _INCB_EXTEND),  # InCB=Extend
    (0x0610, 0x061A, _INCB_EXTEND),  # InCB=Extend
    (0x064B, 0x065F, _INCB_EXTEND),  # InCB=Extend
    (0x0670, 0x0670, _INCB_EXTEND),  # InCB=Extend
    (0x06D6, 0x06DC, _INCB_EXTEND),  # InCB=Extend
    (0x06DF, 0x06E4, _INCB_EXTEND),  # InCB=Extend
    (0x06E7, 0x06E8, _INCB_EXTEND),  # InCB=Extend
    (0x06EA, 0x06ED, _INCB_EXTEND),  # InCB=Extend
    (0x0711, 0x0711, _INCB_EXTEND),  # InCB=Extend
    (0x0730, 0x074A, _INCB_EXTEND),  # InCB=Extend
    (0x07A6, 0x07B0, _INCB_EXTEND),  # InCB=Extend
    (0x07EB, 0x07F3, _INCB_EXTEND),  # InCB=Extend
    (0x07FD, 0x07FD, _INCB_EXTEND),  # InCB=Extend
    (0x0816, 0x0819, _INCB_EXTEND),  # InCB=Extend
    (0x081B, 0x0823, _INCB_EXTEND),  # InCB=Extend
    (0x0825, 0x0827, _INCB_EXTEND),  # InCB=Extend
    (0x0829, 0x082D, _INCB_EXTEND),  # InCB=Extend
    (0x0859, 0x085B, _INCB_EXTEND),  # InCB=Extend
    (0x0897, 0x089F, _INCB_EXTEND),  # InCB=Extend
    (0x08CA, 0x08E1, _INCB_EXTEND),  # InCB=Extend
    (0x08E3, 0x0902, _INCB_EXTEND),  # InCB=Extend
    (0x0915, 0x0939, _INCB_CONSONANT),  # InCB=Consonant
    (0x093A, 0x093A, _INCB_EXTEND),  # InCB=Extend
    (0x093C, 0x093C, _INCB_EXTEND),  # InCB=Extend
    (0x0941, 0x0948, _INCB_EXTEND),  # InCB=Extend
    (0x094D, 0x094D, _INCB_LINKER),  # InCB=Linker
    (0x0951, 0x0957, _INCB_EXTEND),  # InCB=Extend
    (0x0958, 0x095F, _INCB_CONSONANT),  # InCB=Consonant
    (0x0962, 0x0963, _INCB_EXTEND),  # InCB=Extend
    (0x0978, 0x097F, _INCB_CONSONANT),  # InCB=Consonant
    (0x0981, 0x0981, _INCB_EXTEND),  # InCB=Extend
    (0x0995, 0x09A8, _INCB_CONSONANT),  # InCB=Consonant
    (0x09AA, 0x09B0, _INCB_CONSONANT),  # InCB=Consonant
    (0x09B2, 0x09B2, _INCB_CONSONANT),  # InCB=Consonant
    (0x09B6, 0x09B9, _INCB_CONSONANT),  # InCB=Consonant
    (0x09BC, 0x09BC, _INCB_EXTEND),  # InCB=Extend
    (0x09BE, 0x09BE, _INCB_EXTEND),  # InCB=Extend
    (0x09C1, 0x09C4, _INCB_EXTEND),  # InCB=Extend
    (0x09CD, 0x09CD, _INCB_LINKER),  # InCB=Linker
    (0x09D7, 0x09D7, _INCB_EXTEND),  # InCB=Extend
    (0x09DC, 0x09DD, _INCB_CONSONANT),  # InCB=Consonant
    (0x09DF, 0x09DF, _INCB_CONSONANT),  # InCB=Consonant
    (0x09E2, 0x09E3, _INCB_EXTEND),  # InCB=Extend
    (0x09F0, 0x09F1, _INCB_CONSONANT),  # InCB=Consonant
    (0x09FE, 0x09FE, _INCB_EXTEND),  # InCB=Extend
    (0x0A01, 0x0A02, _INCB_EXTEND),  # InCB=Extend
    (0x0A3C, 0x0A3C, _INCB_EXTEND),  # InCB=Extend
    (0x0A41, 0x0A42, _INCB_EXTEND),  # InCB=Extend
    (0x0A47, 0x0A48, _INCB_EXTEND),  # InCB=Extend
    (0x0A4B, 0x0A4D, _INCB_EXTEND),  # InCB=Extend
    (0x0A51, 0x0A51, _INCB_EXTEND),  # InCB=Extend
    (0x0A70, 0x0A71, _INCB_EXTEND),  # InCB=Extend
    (0x0A75, 0x0A75, _INCB_EXTEND),  # InCB=Extend
    (0x0A81, 0x0A82, _INCB_EXTEND),  # InCB=Extend
    (0x0A95, 0x0AA8, _INCB_CONSONANT),  # InCB=Consonant
    (0x0AAA, 0x0AB0, _INCB_CONSONANT),  # InCB=Consonant
    (0x0AB2, 0x0AB3, _INCB_CONSONANT),  # InCB=Consonant
    (0x0AB5, 0x0AB9, _INCB_CONSONANT),  # InCB=Consonant
    (0x0ABC, 0x0ABC, _INCB_EXTEND),  # InCB=Extend
    (0x0AC1, 0x0AC5, _INCB_EXTEND),  # InCB=Extend
    (0x0AC7, 0x0AC8, _INCB_EXTEND),  # InCB=Extend
    (0x0ACD, 0x0ACD, _INCB_LINKER),  # InCB=Linker
    (0x0AE2, 0x0AE3, _INCB_EXTEND),  # InCB=Extend
    (0x0AF9, 0x0AF9, _INCB_CONSONANT),  # InCB=Consonant
    (0x0AFA, 0x0AFF, _INCB_EXTEND),  # InCB=Extend
    (0x0B01, 0x0B01, _INCB_EXTEND),  # InCB=Extend
    (0x0B15, 0x0B28, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B2A, 0x0B30, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B32, 0x0B33, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B35, 0x0B39, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B3C, 0x0B3C, _INCB_EXTEND),  # InCB=Extend
    (0x0B3E, 0x0B3F, _INCB_EXTEND),  # InCB=Extend
    (0x0B41, 0x0B44, _INCB_EXTEND),  # InCB=Extend
    (0x0B4D, 0x0B4D, _INCB_LINKER),  # InCB=Linker
    (0x0B53, 0x0B57, _INCB_EXTEND),  # InCB=Extend
    (0x0B5C, 0x0B5D, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B5F, 0x0B5F, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B62, 0x0B63, _INCB_EXTEND),  # InCB=Extend
    (0x0B71, 0x0B71, _INCB_CONSONANT),  # InCB=Consonant
    (0x0B82, 0x0B82, _INCB_EXTEND),  # InCB=Extend
    (0x0BBE, 0x0BBE, _INCB_EXTEND),  # InCB=Extend
    (0x0BC0, 0x0BC0, _INCB_EXTEND),  # InCB=Extend
    (0x0BCD, 0x0BCD, _INCB_EXTEND),  # InCB=Extend
    (0x0BD7, 0x0BD7, _INCB_EXTEND),  # InCB=Extend
    (0x0C00, 0x0C00, _INCB_EXTEND),  # InCB=Extend
    (0x0C04, 0x0C04, _INCB_EXTEND),  # InCB=Extend
    (0x0C15, 0x0C28, _INCB_CONSONANT),  # InCB=Consonant
    (0x0C2A, 0x0C39, _INCB_CONSONANT),  # InCB=Consonant
    (0x0C3C, 0x0C3C, _INCB_EXTEND),  # InCB=Extend
    (0x0C3E, 0x0C40, _INCB_EXTEND),  # InCB=Extend
    (0x0C46, 0x0C48, _INCB_EXTEND),  # InCB=Extend
    (0x0C4A, 0x0C4C, _INCB_EXTEND),  # InCB=Extend
    (0x0C4D, 0x0C4D, _INCB_LINKER),  # InCB=Linker
    (0x0C55, 0x0C56, _INCB_EXTEND),  # InCB=Extend
    (0x0C58, 0x0C5A, _INCB_CONSONANT),  # InCB=Consonant
    (0x0C62, 0x0C63, _INCB_EXTEND),  # InCB=Extend
    (0x0C81, 0x0C81, _INCB_EXTEND),  # InCB=Extend
    (0x0CBC, 0x0CBC, _INCB_EXTEND),  # InCB=Extend
    (0x0CBF, 0x0CC0, _INCB_EXTEND),  # InCB=Extend
    (0x0CC2, 0x0CC2, _INCB_EXTEND),  # InCB=Extend
    (0x0CC6, 0x0CC8, _INCB_EXTEND),  # InCB=Extend
    (0x0CCA, 0x0CCD, _INCB_EXTEND),  # InCB=Extend
    (0x0CD5, 0x0CD6, _INCB_EXTEND),  # InCB=Extend
    (0x0CE2, 0x0CE3, _INCB_EXTEND),  # InCB=Extend
    (0x0D00, 0x0D01, _INCB_EXTEND),  # InCB=Extend
    (0x0D15, 0x0D3A, _INCB_CONSONANT),  # InCB=Consonant
    (0x0D3B, 0x0D3C, _INCB_EXTEND),  # InCB=Extend
    (0x0D3E, 0x0D3E, _INCB_EXTEND),  # InCB=Extend
    (0x0D41, 0x0D44, _INCB_EXTEND),  # InCB=Extend
    (0x0D4D, 0x0D4D, _INCB_LINKER),  # InCB=Linker
    (0x0D57, 0x0D57, _INCB_EXTEND),  # InCB=Extend
    (0x0D62, 0x0D63, _INCB_EXTEND),  # InCB=Extend
    (0x0D81, 0x0D81, _INCB_EXTEND),  # InCB=Extend
    (0x0DCA, 0x0DCA, _INCB_EXTEND),  # InCB=Extend
    (0x0DCF, 0x0DCF, _INCB_EXTEND),  # InCB=Extend
    (0x0DD2, 0x0DD4, _INCB_EXTEND),  # InCB=Extend
    (0x0DD6, 0x0DD6, _INCB_EXTEND),  # InCB=Extend
    (0x0DDF, 0x0DDF, _INCB_EXTEND),  # InCB=Extend
    (0x0E31, 0x0E31, _INCB_EXTEND),  # InCB=Extend
    (0x0E34, 0x0E3A, _INCB_EXTEND),  # InCB=Extend
    (0x0E47, 0x0E4E, _INCB_EXTEND),  # InCB=Extend
    (0x0EB1, 0x0EB1, _INCB_EXTEND),  # InCB=Extend
    (0x0EB4, 0x0EBC, _INCB_EXTEND),  # InCB=Extend
    (0x0EC8, 0x0ECE, _INCB_EXTEND),  # InCB=Extend
    (0x0F18, 0x0F19, _INCB_EXTEND),  # InCB=Extend
    (0x0F35, 0x0F35, _INCB_EXTEND),  # InCB=Extend
    (0x0F37, 0x0F37, _INCB_EXTEND),  # InCB=Extend
    (0x0F39, 0x0F39, _INCB_EXTEND),  # InCB=Extend
    (0x0F71, 0x0F7E, _INCB_EXTEND),  # InCB=Extend
    (0x0F80, 0x0F84, _INCB_EXTEND),  # InCB=Extend
    (0x0F86, 0x0F87, _INCB_EXTEND),  # InCB=Extend
    (0x0F8D, 0x0F97, _INCB_EXTEND),  # InCB=Extend
    (0x0F99, 0x0FBC, _INCB_EXTEND),  # InCB=Extend
    (0x0FC6, 0x0FC6, _INCB_EXTEND),  # InCB=Extend
    (0x1000, 0x102A, _INCB_CONSONANT),  # InCB=Consonant
    (0x102D, 0x1030, _INCB_EXTEND),  # InCB=Extend
    (0x1032, 0x1037, _INCB_EXTEND),  # InCB=Extend
    (0x1039, 0x1039, _INCB_LINKER),  # InCB=Linker
    (0x103A, 0x103A, _INCB_EXTEND),  # InCB=Extend
    (0x103D, 0x103E, _INCB_EXTEND),  # InCB=Extend
    (0x103F, 0x103F, _INCB_CONSONANT),  # InCB=Consonant
    (0x1050, 0x1055, _INCB_CONSONANT),  # InCB=Consonant
    (0x1058, 0x1059, _INCB_EXTEND),  # InCB=Extend
    (0x105A, 0x105D, _INCB_CONSONANT),  # InCB=Consonant
    (0x105E, 0x1060, _INCB_EXTEND),  # InCB=Extend
    (0x1061, 0x1061, _INCB_CONSONANT),  # InCB=Consonant
    (0x1065, 0x1066, _INCB_CONSONANT),  # InCB=Consonant
    (0x106E, 0x1070, _INCB_CONSONANT),  # InCB=Consonant
    (0x1071, 0x1074, _INCB_EXTEND),  # InCB=Extend
    (0x1075, 0x1081, _INCB_CONSONANT),  # InCB=Consonant
    (0x1082, 0x1082, _INCB_EXTEND),  # InCB=Extend
    (0x1085, 0x1086, _INCB_EXTEND),  # InCB=Extend
    (0x108D, 0x108D, _INCB_EXTEND),  # InCB=Extend
    (0x108E, 0x108E, _INCB_CONSONANT),  # InCB=Consonant
    (0x109D, 0x109D, _INCB_EXTEND),  # InCB=Extend
    (0x135D, 0x135F, _INCB_EXTEND),  # InCB=Extend
    (0x1712, 0x1715, _INCB_EXTEND),  # InCB=Extend
    (0x1732, 0x1734, _INCB_EXTEND),  # InCB=Extend
    (0x1752, 0x1753, _INCB_EXTEND),  # InCB=Extend
    (0x1772, 0x1773, _INCB_EXTEND),  # InCB=Extend
    (0x1780, 0x17B3, _INCB_CONSONANT),  # InCB=Consonant
    (0x17B4, 0x17B5, _INCB_EXTEND),  # InCB=Extend
    (0x17B7, 0x17BD, _INCB_EXTEND),  # InCB=Extend
    (0x17C6, 0x17C6, _INCB_EXTEND),  # InCB=Extend
    (0x17C9, 0x17D1, _INCB_EXTEND),  # InCB=Extend
    (0x17D2, 0x17D2, _INCB_LINKER),  # InCB=Linker
    (0x17D3, 0x17D3, _INCB_EXTEND),  # InCB=Extend
    (0x17DD, 0x17DD, _INCB_EXTEND),  # InCB=Extend
    (0x180B, 0x180D, _INCB_EXTEND),  # InCB=Extend
    (0x180F, 0x180F, _INCB_EXTEND),  # InCB=Extend
    (0x1885, 0x1886, _INCB_EXTEND),  # InCB=Extend
    (0x18A9, 0x18A9, _INCB_EXTEND),  # InCB=Extend
    (0x1920, 0x1922, _INCB_EXTEND),  # InCB=Extend
    (0x1927, 0x1928, _INCB_EXTEND),  # InCB=Extend
    (0x1932, 0x1932, _INCB_EXTEND),  # InCB=Extend
    (0x1939, 0x193B, _INCB_EXTEND),  # InCB=Extend
    (0x1A17, 0x1A18, _INCB_EXTEND),  # InCB=Extend
    (0x1A1B, 0x1A1B, _INCB_EXTEND),  # InCB=Extend
    (0x1A20, 0x1A54, _INCB_CONSONANT),  # InCB=Consonant
    (0x1A56, 0x1A56, _INCB_EXTEND),  # InCB=Extend
    (0x1A58, 0x1A5E, _INCB_EXTEND),  # InCB=Extend
    (0x1A60, 0x1A60, _INCB_LINKER),  # InCB=Linker
    (0x1A62, 0x1A62, _INCB_EXTEND),  # InCB=Extend
    (0x1A65, 0x1A6C, _INCB_EXTEND),  # InCB=Extend
    (0x1A73, 0x1A7C, _INCB_EXTEND),  # InCB=Extend
    (0x1A7F, 0x1A7F, _INCB_EXTEND),  # InCB=Extend
    (0x1AB0, 0x1AF0, _INCB_EXTEND),  # InCB=Extend
    (0x1B00, 0x1B03, _INCB_EXTEND),  # InCB=Extend
    (0x1B0B, 0x1B0C, _INCB_CONSONANT),  # InCB=Consonant
    (0x1B13, 0x1B33, _INCB_CONSONANT),  # InCB=Consonant
    (0x1B34, 0x1B3D, _INCB_EXTEND),  # InCB=Extend
    (0x1B42, 0x1B43, _INCB_EXTEND),  # InCB=Extend
    (0x1B44, 0x1B44, _INCB_LINKER),  # InCB=Linker
    (0x1B45, 0x1B4C, _INCB_CONSONANT),  # InCB=Consonant
    (0x1B6B, 0x1B73, _INCB_EXTEND),  # InCB=Extend
    (0x1B80, 0x1B81, _INCB_EXTEND),  # InCB=Extend
    (0x1B83, 0x1BA0, _INCB_CONSONANT),  # InCB=Consonant
    (0x1BA2, 0x1BA5, _INCB_EXTEND),  # InCB=Extend
    (0x1BA8, 0x1BAA, _INCB_EXTEND),  # InCB=Extend
    (0x1BAB, 0x1BAB, _INCB_LINKER),  # InCB=Linker
    (0x1BAC, 0x1BAD, _INCB_EXTEND),  # InCB=Extend
    (0x1BAE, 0x1BAF, _INCB_CONSONANT),  # InCB=Consonant
    (0x1BBB, 0x1BBD, _INCB_CONSONANT),  # InCB=Consonant
    (0x1BE6, 0x1BE6, _INCB_EXTEND),  # InCB=Extend
    (0x1BE8, 0x1BE9, _INCB_EXTEND),  # InCB=Extend
    (0x1BED, 0x1BED, _INCB_EXTEND),  # InCB=Extend
    (0x1BEF, 0x1BF3, _INCB_EXTEND),  # InCB=Extend
    (0x1C2C, 0x1C33, _INCB_EXTEND),  # InCB=Extend
    (0x1C36, 0x1C37, _INCB_EXTEND),  # InCB=Extend
    (0x1CD0, 0x1CD2, _INCB_EXTEND),  # InCB=Extend
    (0x1CD4, 0x1CE0, _INCB_EXTEND),  # InCB=Extend
    (0x1CE2, 0x1CE8, _INCB_EXTEND),  # InCB=Extend
    (0x1CED, 0x1CED, _INCB_EXTEND),  # InCB=Extend
    (0x1CF4, 0x1CF4, _INCB_EXTEND),  # InCB=Extend
    (0x1CF5, 0x1CF6, _INCB_LINKER),  # InCB=Linker
    (0x1CF8, 0x1CF9, _INCB_EXTEND),  # InCB=Extend
    (0x1DC0, 0x1DFF, _INCB_EXTEND),  # InCB=Extend
    (0x200D, 0x200D, _INCB_EXTEND),  # InCB=Extend
    (0x20D0, 0x20F0, _INCB_EXTEND),  # InCB=Extend
    (0x2CEF, 0x2CF1, _INCB_EXTEND),  # InCB=Extend
    (0x2D7F, 0x2D7F, _INCB_EXTEND),  # InCB=Extend
    (0x2DE0, 0x2DFF, _INCB_EXTEND),  # InCB=Extend
    (0x302A, 0x302F, _INCB_EXTEND),  # InCB=Extend
    (0x3099, 0x309A, _INCB_EXTEND),  # InCB=Extend
    (0xA66F, 0xA672, _INCB_EXTEND),  # InCB=Extend
    (0xA674, 0xA67D, _INCB_EXTEND),  # InCB=Extend
    (0xA69E, 0xA69F, _INCB_EXTEND),  # InCB=Extend
    (0xA6F0, 0xA6F1, _INCB_EXTEND),  # InCB=Extend
    (0xA802, 0xA802, _INCB_EXTEND),  # InCB=Extend
    (0xA806, 0xA806, _INCB_EXTEND),  # InCB=Extend
    (0xA80B, 0xA80B, _INCB_EXTEND),  # InCB=Extend
    (0xA825, 0xA826, _INCB_EXTEND),  # InCB=Extend
    (0xA82C, 0xA82C, _INCB_EXTEND),  # InCB=Extend
    (0xA8C4, 0xA8C5, _INCB_EXTEND),  # InCB=Extend
    (0xA8E0, 0xA8F1, _INCB_EXTEND),  # InCB=Extend
    (0xA8FF, 0xA8FF, _INCB_EXTEND),  # InCB=Extend
    (0xA926, 0xA92D, _INCB_EXTEND),  # InCB=Extend
    (0xA947, 0xA951, _INCB_EXTEND),  # InCB=Extend
    (0xA953, 0xA953, _INCB_EXTEND),  # InCB=Extend
    (0xA980, 0xA982, _INCB_EXTEND),  # InCB=Extend
    (0xA989, 0xA98B, _INCB_CONSONANT),  # InCB=Consonant
    (0xA98F, 0xA9B2, _INCB_CONSONANT),  # InCB=Consonant
    (0xA9B3, 0xA9B3, _INCB_EXTEND),  # InCB=Extend
    (0xA9B6, 0xA9B9, _INCB_EXTEND),  # InCB=Extend
    (0xA9BC, 0xA9BD, _INCB_EXTEND),  # InCB=Extend
    (0xA9C0, 0xA9C0, _INCB_LINKER),  # InCB=Linker
    (0xA9E0, 0xA9E4, _INCB_CONSONANT),  # InCB=Consonant
    (0xA9E5, 0xA9E5, _INCB_EXTEND),  # InCB=Extend
    (0xA9E7, 0xA9EF, _INCB_CONSONANT),  # InCB=Consonant
    (0xA9FA, 0xA9FE, _INCB_CONSONANT),  # InCB=Consonant
    (0xAA29, 0xAA2E, _INCB_EXTEND),  # InCB=Extend
    (0xAA31, 0xAA32, _INCB_EXTEND),  # InCB=Extend
    (0xAA35, 0xAA36, _INCB_EXTEND),  # InCB=Extend
    (0xAA43, 0xAA43, _INCB_EXTEND),  # InCB=Extend
    (0xAA4C, 0xAA4C, _INCB_EXTEND),  # InCB=Extend
    (0xAA60, 0xAA6F, _INCB_CONSONANT),  # InCB=Consonant
    (0xAA71, 0xAA73, _INCB_CONSONANT),  # InCB=Consonant
    (0xAA7A, 0xAA7A, _INCB_CONSONANT),  # InCB=Consonant
    (0xAA7C, 0xAA7C, _INCB_EXTEND),  # InCB=Extend
    (0xAA7E, 0xAA7F, _INCB_CONSONANT),  # InCB=Consonant
    (0xAAB0, 0xAAB0, _INCB_EXTEND),  # InCB=Extend
    (0xAAB2, 0xAAB4, _INCB_EXTEND),  # InCB=Extend
    (0xAAB7, 0xAAB8, _INCB_EXTEND),  # InCB=Extend
    (0xAABE, 0xAABF, _INCB_EXTEND),  # InCB=Extend
    (0xAAC1, 0xAAC1, _INCB_EXTEND),  # InCB=Extend
    (0xAAE0, 0xAAEA, _INCB_CONSONANT),  # InCB=Consonant
    (0xAAEC, 0xAAED, _INCB_EXTEND),  # InCB=Extend
    (0xAAF6, 0xAAF6, _INCB_LINKER),  # InCB=Linker
    (0xABC0, 0xABDA, _INCB_CONSONANT),  # InCB=Consonant
    (0xABE5, 0xABE5, _INCB_EXTEND),  # InCB=Extend
    (0xABE8, 0xABE8, _INCB_EXTEND),  # InCB=Extend
    (0xABED, 0xABED, _INCB_EXTEND),  # InCB=Extend
    (0xFB1E, 0xFB1E, _INCB_EXTEND),  # InCB=Extend
    (0xFE00, 0xFE0F, _INCB_EXTEND),  # InCB=Extend
    (0xFE20, 0xFE2F, _INCB_EXTEND),  # InCB=Extend
    (0xFF9E, 0xFF9F, _INCB_EXTEND),  # InCB=Extend
    (0x101FD, 0x101FD, _INCB_EXTEND),  # InCB=Extend
    (0x102E0, 0x102E0, _INCB_EXTEND),  # InCB=Extend
    (0x10376, 0x1037A, _INCB_EXTEND),  # InCB=Extend
    (0x10A00, 0x10A00, _INCB_CONSONANT),  # InCB=Consonant
    (0x10A01, 0x10A03, _INCB_EXTEND),  # InCB=Extend
    (0x10A05, 0x10A06, _INCB_EXTEND),  # InCB=Extend
    (0x10A0C, 0x10A0F, _INCB_EXTEND),  # InCB=Extend
    (0x10A10, 0x10A13, _INCB_CONSONANT),  # InCB=Consonant
    (0x10A15, 0x10A17, _INCB_CONSONANT),  # InCB=Consonant
    (0x10A19, 0x10A35, _INCB_CONSONANT),  # InCB=Consonant
    (0x10A38, 0x10A3A, _INCB_EXTEND),  # InCB=Extend
    (0x10A3F, 0x10A3F, _INCB_LINKER),  # InCB=Linker
    (0x10AE5, 0x10AE6, _INCB_EXTEND),  # InCB=Extend
    (0x10D24, 0x10D27, _INCB_EXTEND),  # InCB=Extend
    (0x10D69, 0x10D6D, _INCB_EXTEND),  # InCB=Extend
    (0x10EAB, 0x10EAC, _INCB_EXTEND),  # InCB=Extend
    (0x10ECB, 0x10ECF, _INCB_EXTEND),  # InCB=Extend
    (0x10EF0, 0x10EFF, _INCB_EXTEND),  # InCB=Extend
    (0x10F46, 0x10F50, _INCB_EXTEND),  # InCB=Extend
    (0x10F82, 0x10F85, _INCB_EXTEND),  # InCB=Extend
    (0x11001, 0x11001, _INCB_EXTEND),  # InCB=Extend
    (0x11038, 0x11046, _INCB_EXTEND),  # InCB=Extend
    (0x11070, 0x11070, _INCB_EXTEND),  # InCB=Extend
    (0x11073, 0x11074, _INCB_EXTEND),  # InCB=Extend
    (0x1107F, 0x11081, _INCB_EXTEND),  # InCB=Extend
    (0x110B3, 0x110B6, _INCB_EXTEND),  # InCB=Extend
    (0x110B9, 0x110BA, _INCB_EXTEND),  # InCB=Extend
    (0x110C2, 0x110C2, _INCB_EXTEND),  # InCB=Extend
    (0x11100, 0x11102, _INCB_EXTEND),  # InCB=Extend
    (0x11103, 0x11126, _INCB_CONSONANT),  # InCB=Consonant
    (0x11127, 0x1112B, _INCB_EXTEND),  # InCB=Extend
    (0x1112D, 0x11132, _INCB_EXTEND),  # InCB=Extend
    (0x11133, 0x11133, _INCB_LINKER),  # InCB=Linker
    (0x11134, 0x11134, _INCB_EXTEND),  # InCB=Extend
    (0x11144, 0x11144, _INCB_CONSONANT),  # InCB=Consonant
    (0x11147, 0x11147, _INCB_CONSONANT),  # InCB=Consonant
    (0x11173, 0x11173, _INCB_EXTEND),  # InCB=Extend
    (0x11180, 0x11181, _INCB_EXTEND),  # InCB=Extend
    (0x111B6, 0x111BE, _INCB_EXTEND),  # InCB=Extend
    (0x111C0, 0x111C0, _INCB_EXTEND),  # InCB=Extend
    (0x111C9, 0x111CC, _INCB_EXTEND),  # InCB=Extend
    (0x111CF, 0x111CF, _INCB_EXTEND),  # InCB=Extend
    (0x1122F, 0x11231, _INCB_EXTEND),  # InCB=Extend
    (0x11234, 0x11237, _INCB_EXTEND),  # InCB=Extend
    (0x1123E, 0x1123E, _INCB_EXTEND),  # InCB=Extend
    (0x11241, 0x11241, _INCB_EXTEND),  # InCB=Extend
    (0x112DF, 0x112DF, _INCB_EXTEND),  # InCB=Extend
    (0x112E3, 0x112EA, _INCB_EXTEND),  # InCB=Extend
    (0x11300, 0x11301, _INCB_EXTEND),  # InCB=Extend
    (0x1133B, 0x1133C, _INCB_EXTEND),  # InCB=Extend
    (0x1133E, 0x1133E, _INCB_EXTEND),  # InCB=Extend
    (0x11340, 0x11340, _INCB_EXTEND),  # InCB=Extend
    (0x1134D, 0x1134D, _INCB_EXTEND),  # InCB=Extend
    (0x11357, 0x11357, _INCB_EXTEND),  # InCB=Extend
    (0x11366, 0x1136C, _INCB_EXTEND),  # InCB=Extend
    (0x11370, 0x11374, _INCB_EXTEND),  # InCB=Extend
    (0x11380, 0x11389, _INCB_CONSONANT),  # InCB=Consonant
    (0x1138B, 0x1138B, _INCB_CONSONANT),  # InCB=Consonant
    (0x1138E, 0x1138E, _INCB_CONSONANT),  # InCB=Consonant
    (0x11390, 0x113B5, _INCB_CONSONANT),  # InCB=Consonant
    (0x113B8, 0x113B8, _INCB_EXTEND),  # InCB=Extend
    (0x113BB, 0x113C0, _INCB_EXTEND),  # InCB=Extend
    (0x113C2, 0x113C2, _INCB_EXTEND),  # InCB=Extend
    (0x113C5, 0x113C5, _INCB_EXTEND),  # InCB=Extend
    (0x113C7, 0x113C9, _INCB_EXTEND),  # InCB=Extend
    (0x113CE, 0x113CF, _INCB_EXTEND),  # InCB=Extend
    (0x113D0, 0x113D0, _INCB_LINKER),  # InCB=Linker
    (0x113D2, 0x113D2, _INCB_EXTEND),  # InCB=Extend
    (0x113E1, 0x113E2, _INCB_EXTEND),  # InCB=Extend
    (0x11438, 0x1143F, _INCB_EXTEND),  # InCB=Extend
    (0x11442, 0x11444, _INCB_EXTEND),  # InCB=Extend
    (0x11446, 0x11446, _INCB_EXTEND),  # InCB=Extend
    (0x1145E, 0x1145E, _INCB_EXTEND),  # InCB=Extend
    (0x114B0, 0x114B0, _INCB_EXTEND),  # InCB=Extend
    (0x114B3, 0x114B8, _INCB_EXTEND),  # InCB=Extend
    (0x114BA, 0x114BA, _INCB_EXTEND),  # InCB=Extend
    (0x114BD, 0x114BD, _INCB_EXTEND),  # InCB=Extend
    (0x114BF, 0x114C0, _INCB_EXTEND),  # InCB=Extend
    (0x114C2, 0x114C3, _INCB_EXTEND),  # InCB=Extend
    (0x115AF, 0x115AF, _INCB_EXTEND),  # InCB=Extend
    (0x115B2, 0x115B5, _INCB_EXTEND),  # InCB=Extend
    (0x115BC, 0x115BD, _INCB_EXTEND),  # InCB=Extend
    (0x115BF, 0x115C0, _INCB_EXTEND),  # InCB=Extend
    (0x115DC, 0x115DD, _INCB_EXTEND),  # InCB=Extend
    (0x11633, 0x1163A, _INCB_EXTEND),  # InCB=Extend
    (0x1163D, 0x1163D, _INCB_EXTEND),  # InCB=Extend
    (0x1163F, 0x11640, _INCB_EXTEND),  # InCB=Extend
    (0x116AB, 0x116AB, _INCB_EXTEND),  # InCB=Extend
    (0x116AD, 0x116AD, _INCB_EXTEND),  # InCB=Extend
    (0x116B0, 0x116B7, _INCB_EXTEND),  # InCB=Extend
    (0x1171D, 0x1171D, _INCB_EXTEND),  # InCB=Extend
    (0x1171F, 0x1171F, _INCB_EXTEND),  # InCB=Extend
    (0x11722, 0x11725, _INCB_EXTEND),  # InCB=Extend
    (0x11727, 0x1172B, _INCB_EXTEND),  # InCB=Extend
    (0x1182F, 0x11837, _INCB_EXTEND),  # InCB=Extend
    (0x11839, 0x1183A, _INCB_EXTEND),  # InCB=Extend
    (0x11900, 0x11906, _INCB_CONSONANT),  # InCB=Consonant
    (0x11909, 0x11909, _INCB_CONSONANT),  # InCB=Consonant
    (0x1190C, 0x11913, _INCB_CONSONANT),  # InCB=Consonant
    (0x11915, 0x11916, _INCB_CONSONANT),  # InCB=Consonant
    (0x11918, 0x1192F, _INCB_CONSONANT),  # InCB=Consonant
    (0x11930, 0x11930, _INCB_EXTEND),  # InCB=Extend
    (0x1193B, 0x1193D, _INCB_EXTEND),  # InCB=Extend
    (0x1193E, 0x1193E, _INCB_LINKER),  # InCB=Linker
    (0x11943, 0x11943, _INCB_EXTEND),  # InCB=Extend
    (0x119D4, 0x119D7, _INCB_EXTEND),  # InCB=Extend
    (0x119DA, 0x119DB, _INCB_EXTEND),  # InCB=Extend
    (0x119E0, 0x119E0, _INCB_EXTEND),  # InCB=Extend
    (0x11A00, 0x11A00, _INCB_CONSONANT),  # InCB=Consonant
    (0x11A01, 0x11A0A, _INCB_EXTEND),  # InCB=Extend
    (0x11A0B, 0x11A32, _INCB_CONSONANT),  # InCB=Consonant
    (0x11A33, 0x11A38, _INCB_EXTEND),  # InCB=Extend
    (0x11A3A, 0x11A3A, _INCB_LINKER),  # InCB=Linker
    (0x11A3B, 0x11A3E, _INCB_EXTEND),  # InCB=Extend
    (0x11A47, 0x11A47, _INCB_LINKER),  # InCB=Linker
    (0x11A50, 0x11A50, _INCB_CONSONANT),  # InCB=Consonant
    (0x11A51, 0x11A56, _INCB_EXTEND),  # InCB=Extend
    (0x11A59, 0x11A5B, _INCB_EXTEND),  # InCB=Extend
    (0x11A5C, 0x11A83, _INCB_CONSONANT),  # InCB=Consonant
    (0x11A8A, 0x11A96, _INCB_EXTEND),  # InCB=Extend
    (0x11A98, 0x11A98, _INCB_EXTEND),  # InCB=Extend
    (0x11A99, 0x11A99, _INCB_LINKER),  # InCB=Linker
    (0x11B0A, 0x11B0A, _INCB_CONSONANT),  # InCB=Consonant
    (0x11B60, 0x11B60, _INCB_EXTEND),  # InCB=Extend
    (0x11B62, 0x11B64, _INCB_EXTEND),  # InCB=Extend
    (0x11B66, 0x11B66, _INCB_EXTEND),  # InCB=Extend
    (0x11C30, 0x11C36, _INCB_EXTEND),  # InCB=Extend
    (0x11C38, 0x11C3D, _INCB_EXTEND),  # InCB=Extend
    (0x11C3F, 0x11C3F, _INCB_EXTEND),  # InCB=Extend
    (0x11C92, 0x11CA7, _INCB_EXTEND),  # InCB=Extend
    (0x11CAA, 0x11CB0, _INCB_EXTEND),  # InCB=Extend
    (0x11CB2, 0x11CB3, _INCB_EXTEND),  # InCB=Extend
    (0x11CB5, 0x11CB6, _INCB_EXTEND),  # InCB=Extend
    (0x11D31, 0x11D36, _INCB_EXTEND),  # InCB=Extend
    (0x11D3A, 0x11D3A, _INCB_EXTEND),  # InCB=Extend
    (0x11D3C, 0x11D3D, _INCB_EXTEND),  # InCB=Extend
    (0x11D3F, 0x11D45, _INCB_EXTEND),  # InCB=Extend
    (0x11D47, 0x11D47, _INCB_EXTEND),  # InCB=Extend
    (0x11D90, 0x11D91, _INCB_EXTEND),  # InCB=Extend
    (0x11D95, 0x11D95, _INCB_EXTEND),  # InCB=Extend
    (0x11D97, 0x11D97, _INCB_EXTEND),  # InCB=Extend
    (0x11DF0, 0x11DF0, _INCB_EXTEND),  # InCB=Extend
    (0x11DF1, 0x11DF1, _INCB_CONSONANT),  # InCB=Consonant
    (0x11EF3, 0x11EF4, _INCB_EXTEND),  # InCB=Extend
    (0x11F00, 0x11F01, _INCB_EXTEND),  # InCB=Extend
    (0x11F04, 0x11F10, _INCB_CONSONANT),  # InCB=Consonant
    (0x11F12, 0x11F33, _INCB_CONSONANT),  # InCB=Consonant
    (0x11F36, 0x11F3A, _INCB_EXTEND),  # InCB=Extend
    (0x11F40, 0x11F41, _INCB_EXTEND),  # InCB=Extend
    (0x11F42, 0x11F42, _INCB_LINKER),  # InCB=Linker
    (0x11F5A, 0x11F5A, _INCB_EXTEND),  # InCB=Extend
    (0x13440, 0x13440, _INCB_EXTEND),  # InCB=Extend
    (0x13447, 0x13455, _INCB_EXTEND),  # InCB=Extend
    (0x1611E, 0x16129, _INCB_EXTEND),  # InCB=Extend
    (0x1612D, 0x1612F, _INCB_EXTEND),  # InCB=Extend
    (0x16AF0, 0x16AF4, _INCB_EXTEND),  # InCB=Extend
    (0x16B30, 0x16B36, _INCB_EXTEND),  # InCB=Extend
    (0x16F4F, 0x16F4F, _INCB_EXTEND),  # InCB=Extend
    (0x16F8F, 0x16F92, _INCB_EXTEND),  # InCB=Extend
    (0x16FE4, 0x16FE4, _INCB_EXTEND),  # InCB=Extend
    (0x16FF0, 0x16FF1, _INCB_EXTEND),  # InCB=Extend
    (0x1BC9D, 0x1BC9E, _INCB_EXTEND),  # InCB=Extend
    (0x1CF00, 0x1CF2D, _INCB_EXTEND),  # InCB=Extend
    (0x1CF30, 0x1CF46, _INCB_EXTEND),  # InCB=Extend
    (0x1D127, 0x1D128, _INCB_EXTEND),  # InCB=Extend
    (0x1D165, 0x1D169, _INCB_EXTEND),  # InCB=Extend
    (0x1D16D, 0x1D172, _INCB_EXTEND),  # InCB=Extend
    (0x1D17B, 0x1D182, _INCB_EXTEND),  # InCB=Extend
    (0x1D185, 0x1D18B, _INCB_EXTEND),  # InCB=Extend
    (0x1D1AA, 0x1D1AD, _INCB_EXTEND),  # InCB=Extend
    (0x1D242, 0x1D244, _INCB_EXTEND),  # InCB=Extend
    (0x1D250, 0x1D252, _INCB_EXTEND),  # InCB=Extend
    (0x1D25B, 0x1D25C, _INCB_EXTEND),  # InCB=Extend
    (0x1D25F, 0x1D25F, _INCB_EXTEND),  # InCB=Extend
    (0x1D280, 0x1D281, _INCB_EXTEND),  # InCB=Extend
    (0x1DA00, 0x1DA36, _INCB_EXTEND),  # InCB=Extend
    (0x1DA3B, 0x1DA6C, _INCB_EXTEND),  # InCB=Extend
    (0x1DA75, 0x1DA75, _INCB_EXTEND),  # InCB=Extend
    (0x1DA84, 0x1DA84, _INCB_EXTEND),  # InCB=Extend
    (0x1DA9B, 0x1DA9F, _INCB_EXTEND),  # InCB=Extend
    (0x1DAA1, 0x1DAAF, _INCB_EXTEND),  # InCB=Extend
    (0x1E000, 0x1E006, _INCB_EXTEND),  # InCB=Extend
    (0x1E008, 0x1E018, _INCB_EXTEND),  # InCB=Extend
    (0x1E01B, 0x1E021, _INCB_EXTEND),  # InCB=Extend
    (0x1E023, 0x1E024, _INCB_EXTEND),  # InCB=Extend
    (0x1E026, 0x1E02A, _INCB_EXTEND),  # InCB=Extend
    (0x1E08F, 0x1E08F, _INCB_EXTEND),  # InCB=Extend
    (0x1E130, 0x1E136, _INCB_EXTEND),  # InCB=Extend
    (0x1E2AE, 0x1E2AE, _INCB_EXTEND),  # InCB=Extend
    (0x1E2EC, 0x1E2EF, _INCB_EXTEND),  # InCB=Extend
    (0x1E4EC, 0x1E4EF, _INCB_EXTEND),  # InCB=Extend
    (0x1E5EE, 0x1E5EF, _INCB_EXTEND),  # InCB=Extend
    (0x1E6E3, 0x1E6E3, _INCB_EXTEND),  # InCB=Extend
    (0x1E6E6, 0x1E6E6, _INCB_EXTEND),  # InCB=Extend
    (0x1E6EE, 0x1E6EF, _INCB_EXTEND),  # InCB=Extend
    (0x1E6F5, 0x1E6F5, _INCB_EXTEND),  # InCB=Extend
    (0x1E8D0, 0x1E8D6, _INCB_EXTEND),  # InCB=Extend
    (0x1E944, 0x1E94A, _INCB_EXTEND),  # InCB=Extend
    (0x1F3FB, 0x1F3FF, _INCB_EXTEND),  # InCB=Extend
    (0xE0020, 0xE007F, _INCB_EXTEND),  # InCB=Extend
    (0xE0100, 0xE01EF, _INCB_EXTEND),  # InCB=Extend
)
_EXTPICT_RANGES: tuple[tuple[int, int], ...] = (
    (0x00A9, 0x00A9),
    (0x00AE, 0x00AE),
    (0x203C, 0x203C),
    (0x2049, 0x2049),
    (0x2122, 0x2122),
    (0x2139, 0x2139),
    (0x2194, 0x2199),
    (0x21A9, 0x21AA),
    (0x231A, 0x231B),
    (0x2328, 0x2328),
    (0x23CF, 0x23CF),
    (0x23E9, 0x23F3),
    (0x23F8, 0x23FA),
    (0x24C2, 0x24C2),
    (0x25AA, 0x25AB),
    (0x25B6, 0x25B6),
    (0x25C0, 0x25C0),
    (0x25FB, 0x25FE),
    (0x2600, 0x2604),
    (0x260E, 0x260E),
    (0x2611, 0x2611),
    (0x2614, 0x2615),
    (0x2618, 0x2618),
    (0x261D, 0x261D),
    (0x2620, 0x2620),
    (0x2622, 0x2623),
    (0x2626, 0x2626),
    (0x262A, 0x262A),
    (0x262E, 0x262F),
    (0x2638, 0x263A),
    (0x2640, 0x2640),
    (0x2642, 0x2642),
    (0x2648, 0x2653),
    (0x265F, 0x2660),
    (0x2663, 0x2663),
    (0x2665, 0x2666),
    (0x2668, 0x2668),
    (0x267B, 0x267B),
    (0x267E, 0x267F),
    (0x2692, 0x2697),
    (0x2699, 0x2699),
    (0x269B, 0x269C),
    (0x26A0, 0x26A1),
    (0x26A7, 0x26A7),
    (0x26AA, 0x26AB),
    (0x26B0, 0x26B1),
    (0x26BD, 0x26BE),
    (0x26C4, 0x26C5),
    (0x26C8, 0x26C8),
    (0x26CE, 0x26CF),
    (0x26D1, 0x26D1),
    (0x26D3, 0x26D4),
    (0x26E9, 0x26EA),
    (0x26F0, 0x26F5),
    (0x26F7, 0x26FA),
    (0x26FD, 0x26FD),
    (0x2702, 0x2702),
    (0x2705, 0x2705),
    (0x2708, 0x270D),
    (0x270F, 0x270F),
    (0x2712, 0x2712),
    (0x2714, 0x2714),
    (0x2716, 0x2716),
    (0x271D, 0x271D),
    (0x2721, 0x2721),
    (0x2728, 0x2728),
    (0x2733, 0x2734),
    (0x2744, 0x2744),
    (0x2747, 0x2747),
    (0x274C, 0x274C),
    (0x274E, 0x274E),
    (0x2753, 0x2755),
    (0x2757, 0x2757),
    (0x2763, 0x2764),
    (0x2795, 0x2797),
    (0x27A1, 0x27A1),
    (0x27B0, 0x27B0),
    (0x27BF, 0x27BF),
    (0x2934, 0x2935),
    (0x2B05, 0x2B07),
    (0x2B1B, 0x2B1C),
    (0x2B50, 0x2B50),
    (0x2B55, 0x2B55),
    (0x3030, 0x3030),
    (0x303D, 0x303D),
    (0x3297, 0x3297),
    (0x3299, 0x3299),
    (0x1F004, 0x1F004),
    (0x1F02C, 0x1F02F),
    (0x1F094, 0x1F09F),
    (0x1F0AF, 0x1F0B0),
    (0x1F0C0, 0x1F0C0),
    (0x1F0CF, 0x1F0D0),
    (0x1F0F6, 0x1F0FF),
    (0x1F170, 0x1F171),
    (0x1F17E, 0x1F17F),
    (0x1F18E, 0x1F18E),
    (0x1F191, 0x1F19A),
    (0x1F1AF, 0x1F1E5),
    (0x1F201, 0x1F20F),
    (0x1F21A, 0x1F21A),
    (0x1F22F, 0x1F22F),
    (0x1F232, 0x1F23A),
    (0x1F23C, 0x1F23F),
    (0x1F249, 0x1F25F),
    (0x1F266, 0x1F321),
    (0x1F324, 0x1F393),
    (0x1F396, 0x1F397),
    (0x1F399, 0x1F39B),
    (0x1F39E, 0x1F3F0),
    (0x1F3F3, 0x1F3F5),
    (0x1F3F7, 0x1F3FA),
    (0x1F400, 0x1F4FD),
    (0x1F4FF, 0x1F53D),
    (0x1F549, 0x1F54E),
    (0x1F550, 0x1F567),
    (0x1F56F, 0x1F570),
    (0x1F573, 0x1F57A),
    (0x1F587, 0x1F587),
    (0x1F58A, 0x1F58D),
    (0x1F590, 0x1F590),
    (0x1F595, 0x1F596),
    (0x1F5A4, 0x1F5A5),
    (0x1F5A8, 0x1F5A8),
    (0x1F5B1, 0x1F5B2),
    (0x1F5BC, 0x1F5BC),
    (0x1F5C2, 0x1F5C4),
    (0x1F5D1, 0x1F5D3),
    (0x1F5DC, 0x1F5DE),
    (0x1F5E1, 0x1F5E1),
    (0x1F5E3, 0x1F5E3),
    (0x1F5E8, 0x1F5E8),
    (0x1F5EF, 0x1F5EF),
    (0x1F5F3, 0x1F5F3),
    (0x1F5FA, 0x1F64F),
    (0x1F680, 0x1F6C5),
    (0x1F6CB, 0x1F6D2),
    (0x1F6D5, 0x1F6E5),
    (0x1F6E9, 0x1F6E9),
    (0x1F6EB, 0x1F6F0),
    (0x1F6F3, 0x1F6FF),
    (0x1F7DC, 0x1F7F0),
    (0x1F80C, 0x1F80F),
    (0x1F848, 0x1F84F),
    (0x1F85A, 0x1F85F),
    (0x1F888, 0x1F88F),
    (0x1F8AE, 0x1F8AF),
    (0x1F8BC, 0x1F8BF),
    (0x1F8C2, 0x1F8CF),
    (0x1F8D9, 0x1F8FF),
    (0x1F90C, 0x1F93A),
    (0x1F93C, 0x1F945),
    (0x1F947, 0x1F9FF),
    (0x1FA58, 0x1FA5F),
    (0x1FA6E, 0x1FAFF),
    (0x1FC00, 0x1FFFD),
)

_GCB_STARTS, _GCB_ENDS, _GCB_VALUES = _columns(_GCB_RANGES)
_INCB_STARTS, _INCB_ENDS, _INCB_VALUES = _columns(_INCB_RANGES)
_EXTPICT_STARTS: tuple[int, ...] = tuple(start for start, _end in _EXTPICT_RANGES)
_EXTPICT_ENDS: tuple[int, ...] = tuple(end for _start, end in _EXTPICT_RANGES)
