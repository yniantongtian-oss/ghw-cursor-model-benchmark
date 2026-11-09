"""Tests for Unicode grapheme-cluster reversal.

Hand-written cases cover the real-world sequences called out in the
prompt (emoji + skin tone, ZWJ families, combining marks, Chinese).
The official Unicode 15.1 GraphemeBreakTest set is also replayed so
segmentation stays aligned with UAX #29.
"""

from __future__ import annotations

import pytest

from reverse_text import grapheme_clusters, reverse_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _from_hex_clusters(spec: str) -> tuple[str, list[str]]:
    """Decode ``'0041|0301 0042'`` into (joined string, cluster list)."""
    clusters = []
    for piece in spec.split("|"):
        piece = piece.strip()
        if not piece:
            clusters.append("")
            continue
        clusters.append("".join(chr(int(cp, 16)) for cp in piece.split()))
    return "".join(clusters), clusters


def assert_reverses(source: str, expected: str) -> None:
    assert reverse_text(source) == expected
    assert reverse_text(expected) == source
    assert reverse_text(reverse_text(source)) == source


# ---------------------------------------------------------------------------
# Basic / ASCII
# ---------------------------------------------------------------------------

def test_empty_string() -> None:
    assert reverse_text("") == ""
    assert grapheme_clusters("") == []


def test_single_ascii_character() -> None:
    assert reverse_text("a") == "a"
    assert grapheme_clusters("a") == ["a"]


def test_ascii_word() -> None:
    assert_reverses("hello", "olleh")


def test_ascii_with_spaces_and_punctuation() -> None:
    assert_reverses("Hello, world!", "!dlrow ,olleH")


def test_digits_and_symbols() -> None:
    assert_reverses("12+34", "43+21")


# ---------------------------------------------------------------------------
# Combining marks / accents
# ---------------------------------------------------------------------------

def test_combining_acute_stays_with_base() -> None:
    # LATIN SMALL LETTER E + COMBINING ACUTE ACCENT (U+0301)
    clustered = "e\u0301"
    assert grapheme_clusters(clustered) == [clustered]
    assert reverse_text(clustered) == clustered


def test_combining_mark_between_letters() -> None:
    source = "ae\u0301o"
    assert grapheme_clusters(source) == ["a", "e\u0301", "o"]
    assert_reverses(source, "oe\u0301a")


def test_multiple_combining_marks_on_one_base() -> None:
    # Vietnamese-style stack: a + grave + hook above
    stacked = "a\u0300\u0309"
    source = f"x{stacked}y"
    assert grapheme_clusters(source) == ["x", stacked, "y"]
    assert_reverses(source, f"y{stacked}x")


def test_precomposed_and_decomposed_accented_letters() -> None:
    # Precomposed U+00E9 LATIN SMALL LETTER E WITH ACUTE vs e + U+0301.
    precomposed = "caf\u00e9"
    decomposed = "cafe\u0301"
    assert_reverses(precomposed, "\u00e9fac")
    assert grapheme_clusters(decomposed) == ["c", "a", "f", "e\u0301"]
    assert_reverses(decomposed, "e\u0301fac")


def test_combining_enclosing_circle() -> None:
    circled = "a\u20dd"
    assert grapheme_clusters(circled) == [circled]
    assert reverse_text(f"z{circled}") == f"{circled}z"


# ---------------------------------------------------------------------------
# CJK
# ---------------------------------------------------------------------------

def test_chinese_characters_reverse_per_ideograph() -> None:
    assert grapheme_clusters("你好世界") == ["你", "好", "世", "界"]
    assert_reverses("你好世界", "界世好你")


def test_chinese_with_fullwidth_punctuation() -> None:
    source = "你好，世界！"
    assert_reverses(source, "！界世，好你")


def test_japanese_kanji_hiragana_katakana() -> None:
    source = "日本語カタカナひらがな"
    clusters = grapheme_clusters(source)
    assert clusters == list(source)
    assert reverse_text(source) == "".join(reversed(source))


def test_hangul_precomposed_syllables() -> None:
    source = "한글"
    assert grapheme_clusters(source) == ["한", "글"]
    assert_reverses(source, "글한")


def test_hangul_jamo_conjoin_into_one_cluster() -> None:
    # Choseong HIEUH + Jungseong A + Jongseong NIEUN  → one syllable cluster
    jamo = "\u1112\u1161\u11ab"
    assert grapheme_clusters(jamo) == [jamo]
    assert reverse_text(f"a{jamo}b") == f"b{jamo}a"


# ---------------------------------------------------------------------------
# Emoji: skin tones, ZWJ, keycaps, flags, tags
# ---------------------------------------------------------------------------

def test_emoji_with_skin_tone_modifier() -> None:
    waving = "👋🏻"  # U+1F44B U+1F3FB
    assert grapheme_clusters(waving) == [waving]
    assert_reverses(f"a{waving}b", f"b{waving}a")


def test_two_skin_tone_emoji_reverse_as_units() -> None:
    light = "👋🏻"
    dark = "👋🏿"
    assert grapheme_clusters(light + dark) == [light, dark]
    assert_reverses(light + dark, dark + light)


def test_zwj_family_emoji_is_one_cluster() -> None:
    family = "👨‍👩‍👧‍👦"
    assert len(family) > 1  # several code points
    assert grapheme_clusters(family) == [family]
    assert reverse_text(family) == family
    assert_reverses(f"x{family}y", f"y{family}x")


def test_two_zwj_sequences_reverse_without_splitting() -> None:
    family = "👨‍👩‍👧"
    scientist = "👩‍🔬"
    source = family + scientist
    assert grapheme_clusters(source) == [family, scientist]
    assert_reverses(source, scientist + family)


def test_zwj_gendered_profession_with_skin_tone() -> None:
    # woman (dark skin) + ZWJ + microscope
    woman_scientist = "👩🏿‍🔬"
    assert grapheme_clusters(woman_scientist) == [woman_scientist]
    assert_reverses(f"go{woman_scientist}!", f"!{woman_scientist}og")


def test_rainbow_flag_zwj_sequence() -> None:
    rainbow_flag = "🏳️‍🌈"  # white flag + VS16 + ZWJ + rainbow
    assert grapheme_clusters(rainbow_flag) == [rainbow_flag]
    assert reverse_text(f"[{rainbow_flag}]") == f"]{rainbow_flag}["


def test_keycap_emoji() -> None:
    keycap = "1️⃣"  # digit 1 + VS16 + combining enclosing keycap
    assert grapheme_clusters(keycap) == [keycap]
    assert_reverses(f"#{keycap}", f"{keycap}#")


def test_regional_indicator_flag_pair() -> None:
    us = "🇺🇸"
    de = "🇩🇪"
    assert grapheme_clusters(us) == [us]
    assert grapheme_clusters(us + de) == [us, de]
    assert_reverses(us + de, de + us)


def test_odd_number_of_regional_indicators_pairs_from_the_start() -> None:
    # Three RIs → (RI RI) + leftover RI
    three = "\U0001f1fa\U0001f1f8\U0001f1e9"  # US + lone D
    clusters = grapheme_clusters(three)
    assert len(clusters) == 2
    assert reverse_text(three) == "".join(reversed(clusters))


def test_emoji_tag_sequence_england_flag() -> None:
    # black flag + tag latin letters g b e n g + cancel tag
    england = "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
    assert grapheme_clusters(england) == [england]
    assert_reverses(f"a{england}b", f"b{england}a")


def test_variation_selector_16_keeps_emoji_presentation() -> None:
    heart = "❤️"  # U+2764 U+FE0F
    assert grapheme_clusters(heart) == [heart]
    assert_reverses(f"x{heart}y", f"y{heart}x")


# ---------------------------------------------------------------------------
# Controls, newlines, mixed scripts
# ---------------------------------------------------------------------------

def test_crlf_is_a_single_cluster() -> None:
    crlf = "\r\n"
    assert grapheme_clusters(crlf) == [crlf]
    assert grapheme_clusters("a\r\nb") == ["a", crlf, "b"]
    assert reverse_text("a\r\nb") == "b\r\na"


def test_lone_lf_and_cr_are_separate() -> None:
    assert grapheme_clusters("a\nb") == ["a", "\n", "b"]
    assert reverse_text("a\nb") == "b\na"
    assert grapheme_clusters("\r") == ["\r"]


def test_mixed_scripts_emoji_and_chinese() -> None:
    source = "Hello, 世界👋🏻!"
    clusters = grapheme_clusters(source)
    assert "世" in clusters and "界" in clusters
    assert "👋🏻" in clusters
    assert reverse_text(source) == "".join(reversed(clusters))
    assert reverse_text(reverse_text(source)) == source


def test_devanagari_conjunct_ka_virama_ssa() -> None:
    # UAX #29 GB9c: क + virama + ष stay one cluster in Unicode 15.1+
    conjunct = "\u0915\u094d\u0937"  # क्ष
    assert grapheme_clusters(conjunct) == [conjunct]
    assert_reverses(f"a{conjunct}b", f"b{conjunct}a")


def test_zwj_and_skin_tone_do_not_cross_cluster_boundaries() -> None:
    source = "A👋🏻👨‍👩‍👧Z"
    clusters = grapheme_clusters(source)
    assert clusters[0] == "A"
    assert clusters[-1] == "Z"
    assert reverse_text(source) == "".join(reversed(clusters))
    assert reverse_text(reverse_text(source)) == source


def test_long_string_round_trip() -> None:
    source = "αβγ " + "你好" + " 👋🏻 " + "👨‍👩‍👧‍👦" + " café e\u0301 한글 🇺🇸"
    assert reverse_text(reverse_text(source)) == source
    assert len(grapheme_clusters(source)) < len(source)


def test_prepend_makes_round_trip_asymmetric() -> None:
    """U+0600 ARABIC NUMBER SIGN is Prepend: it binds to the *following* cluster.

    Reversing ``'a' + Prepend`` yields ``Prepend + 'a'``, which UAX #29 then
    treats as a single cluster, so a second reverse does not restore the
    original. This is a property of the segmentation rules, not a bug.
    """
    prepend = "\u0600"
    source = "a" + prepend
    assert grapheme_clusters(source) == ["a", prepend]
    reversed_once = reverse_text(source)
    assert reversed_once == prepend + "a"
    assert grapheme_clusters(reversed_once) == [prepend + "a"]
    assert reverse_text(reversed_once) == prepend + "a"
    assert reverse_text(reversed_once) != source


# ---------------------------------------------------------------------------
# Official Unicode 15.1 extended grapheme cluster tests
# ---------------------------------------------------------------------------

# Source: https://www.unicode.org/Public/15.1.0/ucd/auxiliary/GraphemeBreakTest.txt
_UAX29_GRAPHEMEBREAKTEST = """
0020|0020
0020 0308|0020
0020|000D
0020 0308|000D
0020|000A
0020 0308|000A
0020|0001
0020 0308|0001
0020 034F
0020 0308 034F
0020|1F1E6
0020 0308|1F1E6
0020|0600
0020 0308|0600
0020 0A03
0020 0308 0A03
0020|1100
0020 0308|1100
0020|1160
0020 0308|1160
0020|11A8
0020 0308|11A8
0020|AC00
0020 0308|AC00
0020|AC01
0020 0308|AC01
0020 0900
0020 0308 0900
0020 0903
0020 0308 0903
0020|0904
0020 0308|0904
0020|0D4E
0020 0308|0D4E
0020|0915
0020 0308|0915
0020|231A
0020 0308|231A
0020 0300
0020 0308 0300
0020 093C
0020 0308 093C
0020 094D
0020 0308 094D
0020 200D
0020 0308 200D
0020|0378
0020 0308|0378
000D|0020
000D|0308|0020
000D|000D
000D|0308|000D
000D 000A
000D|0308|000A
000D|0001
000D|0308|0001
000D|034F
000D|0308 034F
000D|1F1E6
000D|0308|1F1E6
000D|0600
000D|0308|0600
000D|0A03
000D|0308 0A03
000D|1100
000D|0308|1100
000D|1160
000D|0308|1160
000D|11A8
000D|0308|11A8
000D|AC00
000D|0308|AC00
000D|AC01
000D|0308|AC01
000D|0900
000D|0308 0900
000D|0903
000D|0308 0903
000D|0904
000D|0308|0904
000D|0D4E
000D|0308|0D4E
000D|0915
000D|0308|0915
000D|231A
000D|0308|231A
000D|0300
000D|0308 0300
000D|093C
000D|0308 093C
000D|094D
000D|0308 094D
000D|200D
000D|0308 200D
000D|0378
000D|0308|0378
000A|0020
000A|0308|0020
000A|000D
000A|0308|000D
000A|000A
000A|0308|000A
000A|0001
000A|0308|0001
000A|034F
000A|0308 034F
000A|1F1E6
000A|0308|1F1E6
000A|0600
000A|0308|0600
000A|0A03
000A|0308 0A03
000A|1100
000A|0308|1100
000A|1160
000A|0308|1160
000A|11A8
000A|0308|11A8
000A|AC00
000A|0308|AC00
000A|AC01
000A|0308|AC01
000A|0900
000A|0308 0900
000A|0903
000A|0308 0903
000A|0904
000A|0308|0904
000A|0D4E
000A|0308|0D4E
000A|0915
000A|0308|0915
000A|231A
000A|0308|231A
000A|0300
000A|0308 0300
000A|093C
000A|0308 093C
000A|094D
000A|0308 094D
000A|200D
000A|0308 200D
000A|0378
000A|0308|0378
0001|0020
0001|0308|0020
0001|000D
0001|0308|000D
0001|000A
0001|0308|000A
0001|0001
0001|0308|0001
0001|034F
0001|0308 034F
0001|1F1E6
0001|0308|1F1E6
0001|0600
0001|0308|0600
0001|0A03
0001|0308 0A03
0001|1100
0001|0308|1100
0001|1160
0001|0308|1160
0001|11A8
0001|0308|11A8
0001|AC00
0001|0308|AC00
0001|AC01
0001|0308|AC01
0001|0900
0001|0308 0900
0001|0903
0001|0308 0903
0001|0904
0001|0308|0904
0001|0D4E
0001|0308|0D4E
0001|0915
0001|0308|0915
0001|231A
0001|0308|231A
0001|0300
0001|0308 0300
0001|093C
0001|0308 093C
0001|094D
0001|0308 094D
0001|200D
0001|0308 200D
0001|0378
0001|0308|0378
034F|0020
034F 0308|0020
034F|000D
034F 0308|000D
034F|000A
034F 0308|000A
034F|0001
034F 0308|0001
034F 034F
034F 0308 034F
034F|1F1E6
034F 0308|1F1E6
034F|0600
034F 0308|0600
034F 0A03
034F 0308 0A03
034F|1100
034F 0308|1100
034F|1160
034F 0308|1160
034F|11A8
034F 0308|11A8
034F|AC00
034F 0308|AC00
034F|AC01
034F 0308|AC01
034F 0900
034F 0308 0900
034F 0903
034F 0308 0903
034F|0904
034F 0308|0904
034F|0D4E
034F 0308|0D4E
034F|0915
034F 0308|0915
034F|231A
034F 0308|231A
034F 0300
034F 0308 0300
034F 093C
034F 0308 093C
034F 094D
034F 0308 094D
034F 200D
034F 0308 200D
034F|0378
034F 0308|0378
1F1E6|0020
1F1E6 0308|0020
1F1E6|000D
1F1E6 0308|000D
1F1E6|000A
1F1E6 0308|000A
1F1E6|0001
1F1E6 0308|0001
1F1E6 034F
1F1E6 0308 034F
1F1E6 1F1E6
1F1E6 0308|1F1E6
1F1E6|0600
1F1E6 0308|0600
1F1E6 0A03
1F1E6 0308 0A03
1F1E6|1100
1F1E6 0308|1100
1F1E6|1160
1F1E6 0308|1160
1F1E6|11A8
1F1E6 0308|11A8
1F1E6|AC00
1F1E6 0308|AC00
1F1E6|AC01
1F1E6 0308|AC01
1F1E6 0900
1F1E6 0308 0900
1F1E6 0903
1F1E6 0308 0903
1F1E6|0904
1F1E6 0308|0904
1F1E6|0D4E
1F1E6 0308|0D4E
1F1E6|0915
1F1E6 0308|0915
1F1E6|231A
1F1E6 0308|231A
1F1E6 0300
1F1E6 0308 0300
1F1E6 093C
1F1E6 0308 093C
1F1E6 094D
1F1E6 0308 094D
1F1E6 200D
1F1E6 0308 200D
1F1E6|0378
1F1E6 0308|0378
0600 0020
0600 0308|0020
0600|000D
0600 0308|000D
0600|000A
0600 0308|000A
0600|0001
0600 0308|0001
0600 034F
0600 0308 034F
0600 1F1E6
0600 0308|1F1E6
0600 0600
0600 0308|0600
0600 0A03
0600 0308 0A03
0600 1100
0600 0308|1100
0600 1160
0600 0308|1160
0600 11A8
0600 0308|11A8
0600 AC00
0600 0308|AC00
0600 AC01
0600 0308|AC01
0600 0900
0600 0308 0900
0600 0903
0600 0308 0903
0600 0904
0600 0308|0904
0600 0D4E
0600 0308|0D4E
0600 0915
0600 0308|0915
0600 231A
0600 0308|231A
0600 0300
0600 0308 0300
0600 093C
0600 0308 093C
0600 094D
0600 0308 094D
0600 200D
0600 0308 200D
0600 0378
0600 0308|0378
0A03|0020
0A03 0308|0020
0A03|000D
0A03 0308|000D
0A03|000A
0A03 0308|000A
0A03|0001
0A03 0308|0001
0A03 034F
0A03 0308 034F
0A03|1F1E6
0A03 0308|1F1E6
0A03|0600
0A03 0308|0600
0A03 0A03
0A03 0308 0A03
0A03|1100
0A03 0308|1100
0A03|1160
0A03 0308|1160
0A03|11A8
0A03 0308|11A8
0A03|AC00
0A03 0308|AC00
0A03|AC01
0A03 0308|AC01
0A03 0900
0A03 0308 0900
0A03 0903
0A03 0308 0903
0A03|0904
0A03 0308|0904
0A03|0D4E
0A03 0308|0D4E
0A03|0915
0A03 0308|0915
0A03|231A
0A03 0308|231A
0A03 0300
0A03 0308 0300
0A03 093C
0A03 0308 093C
0A03 094D
0A03 0308 094D
0A03 200D
0A03 0308 200D
0A03|0378
0A03 0308|0378
1100|0020
1100 0308|0020
1100|000D
1100 0308|000D
1100|000A
1100 0308|000A
1100|0001
1100 0308|0001
1100 034F
1100 0308 034F
1100|1F1E6
1100 0308|1F1E6
1100|0600
1100 0308|0600
1100 0A03
1100 0308 0A03
1100 1100
1100 0308|1100
1100 1160
1100 0308|1160
1100|11A8
1100 0308|11A8
1100 AC00
1100 0308|AC00
1100 AC01
1100 0308|AC01
1100 0900
1100 0308 0900
1100 0903
1100 0308 0903
1100|0904
1100 0308|0904
1100|0D4E
1100 0308|0D4E
1100|0915
1100 0308|0915
1100|231A
1100 0308|231A
1100 0300
1100 0308 0300
1100 093C
1100 0308 093C
1100 094D
1100 0308 094D
1100 200D
1100 0308 200D
1100|0378
1100 0308|0378
1160|0020
1160 0308|0020
1160|000D
1160 0308|000D
1160|000A
1160 0308|000A
1160|0001
1160 0308|0001
1160 034F
1160 0308 034F
1160|1F1E6
1160 0308|1F1E6
1160|0600
1160 0308|0600
1160 0A03
1160 0308 0A03
1160|1100
1160 0308|1100
1160 1160
1160 0308|1160
1160 11A8
1160 0308|11A8
1160|AC00
1160 0308|AC00
1160|AC01
1160 0308|AC01
1160 0900
1160 0308 0900
1160 0903
1160 0308 0903
1160|0904
1160 0308|0904
1160|0D4E
1160 0308|0D4E
1160|0915
1160 0308|0915
1160|231A
1160 0308|231A
1160 0300
1160 0308 0300
1160 093C
1160 0308 093C
1160 094D
1160 0308 094D
1160 200D
1160 0308 200D
1160|0378
1160 0308|0378
11A8|0020
11A8 0308|0020
11A8|000D
11A8 0308|000D
11A8|000A
11A8 0308|000A
11A8|0001
11A8 0308|0001
11A8 034F
11A8 0308 034F
11A8|1F1E6
11A8 0308|1F1E6
11A8|0600
11A8 0308|0600
11A8 0A03
11A8 0308 0A03
11A8|1100
11A8 0308|1100
11A8|1160
11A8 0308|1160
11A8 11A8
11A8 0308|11A8
11A8|AC00
11A8 0308|AC00
11A8|AC01
11A8 0308|AC01
11A8 0900
11A8 0308 0900
11A8 0903
11A8 0308 0903
11A8|0904
11A8 0308|0904
11A8|0D4E
11A8 0308|0D4E
11A8|0915
11A8 0308|0915
11A8|231A
11A8 0308|231A
11A8 0300
11A8 0308 0300
11A8 093C
11A8 0308 093C
11A8 094D
11A8 0308 094D
11A8 200D
11A8 0308 200D
11A8|0378
11A8 0308|0378
AC00|0020
AC00 0308|0020
AC00|000D
AC00 0308|000D
AC00|000A
AC00 0308|000A
AC00|0001
AC00 0308|0001
AC00 034F
AC00 0308 034F
AC00|1F1E6
AC00 0308|1F1E6
AC00|0600
AC00 0308|0600
AC00 0A03
AC00 0308 0A03
AC00|1100
AC00 0308|1100
AC00 1160
AC00 0308|1160
AC00 11A8
AC00 0308|11A8
AC00|AC00
AC00 0308|AC00
AC00|AC01
AC00 0308|AC01
AC00 0900
AC00 0308 0900
AC00 0903
AC00 0308 0903
AC00|0904
AC00 0308|0904
AC00|0D4E
AC00 0308|0D4E
AC00|0915
AC00 0308|0915
AC00|231A
AC00 0308|231A
AC00 0300
AC00 0308 0300
AC00 093C
AC00 0308 093C
AC00 094D
AC00 0308 094D
AC00 200D
AC00 0308 200D
AC00|0378
AC00 0308|0378
AC01|0020
AC01 0308|0020
AC01|000D
AC01 0308|000D
AC01|000A
AC01 0308|000A
AC01|0001
AC01 0308|0001
AC01 034F
AC01 0308 034F
AC01|1F1E6
AC01 0308|1F1E6
AC01|0600
AC01 0308|0600
AC01 0A03
AC01 0308 0A03
AC01|1100
AC01 0308|1100
AC01|1160
AC01 0308|1160
AC01 11A8
AC01 0308|11A8
AC01|AC00
AC01 0308|AC00
AC01|AC01
AC01 0308|AC01
AC01 0900
AC01 0308 0900
AC01 0903
AC01 0308 0903
AC01|0904
AC01 0308|0904
AC01|0D4E
AC01 0308|0D4E
AC01|0915
AC01 0308|0915
AC01|231A
AC01 0308|231A
AC01 0300
AC01 0308 0300
AC01 093C
AC01 0308 093C
AC01 094D
AC01 0308 094D
AC01 200D
AC01 0308 200D
AC01|0378
AC01 0308|0378
0900|0020
0900 0308|0020
0900|000D
0900 0308|000D
0900|000A
0900 0308|000A
0900|0001
0900 0308|0001
0900 034F
0900 0308 034F
0900|1F1E6
0900 0308|1F1E6
0900|0600
0900 0308|0600
0900 0A03
0900 0308 0A03
0900|1100
0900 0308|1100
0900|1160
0900 0308|1160
0900|11A8
0900 0308|11A8
0900|AC00
0900 0308|AC00
0900|AC01
0900 0308|AC01
0900 0900
0900 0308 0900
0900 0903
0900 0308 0903
0900|0904
0900 0308|0904
0900|0D4E
0900 0308|0D4E
0900|0915
0900 0308|0915
0900|231A
0900 0308|231A
0900 0300
0900 0308 0300
0900 093C
0900 0308 093C
0900 094D
0900 0308 094D
0900 200D
0900 0308 200D
0900|0378
0900 0308|0378
0903|0020
0903 0308|0020
0903|000D
0903 0308|000D
0903|000A
0903 0308|000A
0903|0001
0903 0308|0001
0903 034F
0903 0308 034F
0903|1F1E6
0903 0308|1F1E6
0903|0600
0903 0308|0600
0903 0A03
0903 0308 0A03
0903|1100
0903 0308|1100
0903|1160
0903 0308|1160
0903|11A8
0903 0308|11A8
0903|AC00
0903 0308|AC00
0903|AC01
0903 0308|AC01
0903 0900
0903 0308 0900
0903 0903
0903 0308 0903
0903|0904
0903 0308|0904
0903|0D4E
0903 0308|0D4E
0903|0915
0903 0308|0915
0903|231A
0903 0308|231A
0903 0300
0903 0308 0300
0903 093C
0903 0308 093C
0903 094D
0903 0308 094D
0903 200D
0903 0308 200D
0903|0378
0903 0308|0378
0904|0020
0904 0308|0020
0904|000D
0904 0308|000D
0904|000A
0904 0308|000A
0904|0001
0904 0308|0001
0904 034F
0904 0308 034F
0904|1F1E6
0904 0308|1F1E6
0904|0600
0904 0308|0600
0904 0A03
0904 0308 0A03
0904|1100
0904 0308|1100
0904|1160
0904 0308|1160
0904|11A8
0904 0308|11A8
0904|AC00
0904 0308|AC00
0904|AC01
0904 0308|AC01
0904 0900
0904 0308 0900
0904 0903
0904 0308 0903
0904|0904
0904 0308|0904
0904|0D4E
0904 0308|0D4E
0904|0915
0904 0308|0915
0904|231A
0904 0308|231A
0904 0300
0904 0308 0300
0904 093C
0904 0308 093C
0904 094D
0904 0308 094D
0904 200D
0904 0308 200D
0904|0378
0904 0308|0378
0D4E 0020
0D4E 0308|0020
0D4E|000D
0D4E 0308|000D
0D4E|000A
0D4E 0308|000A
0D4E|0001
0D4E 0308|0001
0D4E 034F
0D4E 0308 034F
0D4E 1F1E6
0D4E 0308|1F1E6
0D4E 0600
0D4E 0308|0600
0D4E 0A03
0D4E 0308 0A03
0D4E 1100
0D4E 0308|1100
0D4E 1160
0D4E 0308|1160
0D4E 11A8
0D4E 0308|11A8
0D4E AC00
0D4E 0308|AC00
0D4E AC01
0D4E 0308|AC01
0D4E 0900
0D4E 0308 0900
0D4E 0903
0D4E 0308 0903
0D4E 0904
0D4E 0308|0904
0D4E 0D4E
0D4E 0308|0D4E
0D4E 0915
0D4E 0308|0915
0D4E 231A
0D4E 0308|231A
0D4E 0300
0D4E 0308 0300
0D4E 093C
0D4E 0308 093C
0D4E 094D
0D4E 0308 094D
0D4E 200D
0D4E 0308 200D
0D4E 0378
0D4E 0308|0378
0915|0020
0915 0308|0020
0915|000D
0915 0308|000D
0915|000A
0915 0308|000A
0915|0001
0915 0308|0001
0915 034F
0915 0308 034F
0915|1F1E6
0915 0308|1F1E6
0915|0600
0915 0308|0600
0915 0A03
0915 0308 0A03
0915|1100
0915 0308|1100
0915|1160
0915 0308|1160
0915|11A8
0915 0308|11A8
0915|AC00
0915 0308|AC00
0915|AC01
0915 0308|AC01
0915 0900
0915 0308 0900
0915 0903
0915 0308 0903
0915|0904
0915 0308|0904
0915|0D4E
0915 0308|0D4E
0915|0915
0915 0308|0915
0915|231A
0915 0308|231A
0915 0300
0915 0308 0300
0915 093C
0915 0308 093C
0915 094D
0915 0308 094D
0915 200D
0915 0308 200D
0915|0378
0915 0308|0378
231A|0020
231A 0308|0020
231A|000D
231A 0308|000D
231A|000A
231A 0308|000A
231A|0001
231A 0308|0001
231A 034F
231A 0308 034F
231A|1F1E6
231A 0308|1F1E6
231A|0600
231A 0308|0600
231A 0A03
231A 0308 0A03
231A|1100
231A 0308|1100
231A|1160
231A 0308|1160
231A|11A8
231A 0308|11A8
231A|AC00
231A 0308|AC00
231A|AC01
231A 0308|AC01
231A 0900
231A 0308 0900
231A 0903
231A 0308 0903
231A|0904
231A 0308|0904
231A|0D4E
231A 0308|0D4E
231A|0915
231A 0308|0915
231A|231A
231A 0308|231A
231A 0300
231A 0308 0300
231A 093C
231A 0308 093C
231A 094D
231A 0308 094D
231A 200D
231A 0308 200D
231A|0378
231A 0308|0378
0300|0020
0300 0308|0020
0300|000D
0300 0308|000D
0300|000A
0300 0308|000A
0300|0001
0300 0308|0001
0300 034F
0300 0308 034F
0300|1F1E6
0300 0308|1F1E6
0300|0600
0300 0308|0600
0300 0A03
0300 0308 0A03
0300|1100
0300 0308|1100
0300|1160
0300 0308|1160
0300|11A8
0300 0308|11A8
0300|AC00
0300 0308|AC00
0300|AC01
0300 0308|AC01
0300 0900
0300 0308 0900
0300 0903
0300 0308 0903
0300|0904
0300 0308|0904
0300|0D4E
0300 0308|0D4E
0300|0915
0300 0308|0915
0300|231A
0300 0308|231A
0300 0300
0300 0308 0300
0300 093C
0300 0308 093C
0300 094D
0300 0308 094D
0300 200D
0300 0308 200D
0300|0378
0300 0308|0378
093C|0020
093C 0308|0020
093C|000D
093C 0308|000D
093C|000A
093C 0308|000A
093C|0001
093C 0308|0001
093C 034F
093C 0308 034F
093C|1F1E6
093C 0308|1F1E6
093C|0600
093C 0308|0600
093C 0A03
093C 0308 0A03
093C|1100
093C 0308|1100
093C|1160
093C 0308|1160
093C|11A8
093C 0308|11A8
093C|AC00
093C 0308|AC00
093C|AC01
093C 0308|AC01
093C 0900
093C 0308 0900
093C 0903
093C 0308 0903
093C|0904
093C 0308|0904
093C|0D4E
093C 0308|0D4E
093C|0915
093C 0308|0915
093C|231A
093C 0308|231A
093C 0300
093C 0308 0300
093C 093C
093C 0308 093C
093C 094D
093C 0308 094D
093C 200D
093C 0308 200D
093C|0378
093C 0308|0378
094D|0020
094D 0308|0020
094D|000D
094D 0308|000D
094D|000A
094D 0308|000A
094D|0001
094D 0308|0001
094D 034F
094D 0308 034F
094D|1F1E6
094D 0308|1F1E6
094D|0600
094D 0308|0600
094D 0A03
094D 0308 0A03
094D|1100
094D 0308|1100
094D|1160
094D 0308|1160
094D|11A8
094D 0308|11A8
094D|AC00
094D 0308|AC00
094D|AC01
094D 0308|AC01
094D 0900
094D 0308 0900
094D 0903
094D 0308 0903
094D|0904
094D 0308|0904
094D|0D4E
094D 0308|0D4E
094D|0915
094D 0308|0915
094D|231A
094D 0308|231A
094D 0300
094D 0308 0300
094D 093C
094D 0308 093C
094D 094D
094D 0308 094D
094D 200D
094D 0308 200D
094D|0378
094D 0308|0378
200D|0020
200D 0308|0020
200D|000D
200D 0308|000D
200D|000A
200D 0308|000A
200D|0001
200D 0308|0001
200D 034F
200D 0308 034F
200D|1F1E6
200D 0308|1F1E6
200D|0600
200D 0308|0600
200D 0A03
200D 0308 0A03
200D|1100
200D 0308|1100
200D|1160
200D 0308|1160
200D|11A8
200D 0308|11A8
200D|AC00
200D 0308|AC00
200D|AC01
200D 0308|AC01
200D 0900
200D 0308 0900
200D 0903
200D 0308 0903
200D|0904
200D 0308|0904
200D|0D4E
200D 0308|0D4E
200D|0915
200D 0308|0915
200D|231A
200D 0308|231A
200D 0300
200D 0308 0300
200D 093C
200D 0308 093C
200D 094D
200D 0308 094D
200D 200D
200D 0308 200D
200D|0378
200D 0308|0378
0378|0020
0378 0308|0020
0378|000D
0378 0308|000D
0378|000A
0378 0308|000A
0378|0001
0378 0308|0001
0378 034F
0378 0308 034F
0378|1F1E6
0378 0308|1F1E6
0378|0600
0378 0308|0600
0378 0A03
0378 0308 0A03
0378|1100
0378 0308|1100
0378|1160
0378 0308|1160
0378|11A8
0378 0308|11A8
0378|AC00
0378 0308|AC00
0378|AC01
0378 0308|AC01
0378 0900
0378 0308 0900
0378 0903
0378 0308 0903
0378|0904
0378 0308|0904
0378|0D4E
0378 0308|0D4E
0378|0915
0378 0308|0915
0378|231A
0378 0308|231A
0378 0300
0378 0308 0300
0378 093C
0378 0308 093C
0378 094D
0378 0308 094D
0378 200D
0378 0308 200D
0378|0378
0378 0308|0378
000D 000A|0061|000A|0308
0061 0308
0020 200D|0646
0646 200D|0020
AC00 11A8|1100
AC01 11A8|1100
1F1E6 1F1E7|1F1E8|0062
0061|1F1E6 1F1E7|1F1E8|0062
0061|1F1E6 1F1E7 200D|1F1E8|0062
0061|1F1E6 200D|1F1E7 1F1E8|0062
0061|1F1E6 1F1E7|1F1E8 1F1E9|0062
0061 200D
0061 0308|0062
0061 0903|0062
0061|0600 0062
1F476 1F3FF|1F476
0061 1F3FF|1F476
0061 1F3FF|1F476 200D 1F6D1
1F476 1F3FF 0308 200D 1F476 1F3FF
1F6D1 200D 1F6D1
0061 200D|1F6D1
2701 200D 2701
0061 200D|2701
0915|0924
0915 094D 0924
0915 094D 094D 0924
0915 094D 200D 0924
0915 093C 200D 094D 0924
0915 093C 094D 200D 0924
0915 094D 0924 094D 092F
0915 094D|0061
0061 094D|0924
003F 094D|0924
"""


def _official_specs() -> list[str]:
    # Compact encoding of GraphemeBreakTest-15.1.0.txt: each line is
    # space-separated code points inside a cluster, clusters split by '|'.
    return [line for line in _UAX29_GRAPHEMEBREAKTEST.strip().splitlines() if line]


@pytest.mark.parametrize("spec", _official_specs())
def test_uax29_grapheme_break_test(spec: str) -> None:
    source, expected = _from_hex_clusters(spec)
    assert grapheme_clusters(source) == expected
    # Reverse is defined on the cluster list. Re-segmenting the reversed
    # string is not always the inverse: Prepend, Extend, RI pairing, and
    # Hangul jamo are directional under UAX #29.
    assert reverse_text(source) == "".join(reversed(expected))
