"""Tests for Unicode-aware string reversal."""

import unicodedata

import pytest

from reverse_text import reverse_text


def test_empty_and_ascii():
    assert reverse_text("") == ""
    assert reverse_text("a") == "a"
    assert reverse_text("hello") == "olleh"
    assert reverse_text("racecar") == "racecar"


def test_chinese():
    assert reverse_text("你好世界") == "界世好你"
    assert reverse_text("中文") == "文中"


def test_combining_accent_precomposed():
    assert reverse_text("café") == "éfac"


def test_combining_accent_decomposed():
    e_acute = "e\u0301"
    assert reverse_text(f"caf{e_acute}") == f"{e_acute}fac"


def test_multiple_combining_marks():
    # g + acute + combining ring above -> one grapheme
    g_marked = "g\u0301\u030A"
    assert reverse_text("a" + g_marked + "b") == "b" + g_marked + "a"


def test_emoji_skin_tone():
    wave_medium = "\U0001F44B\U0001F3FD"  # 👋🏽
    assert reverse_text(f"Hi {wave_medium}") == f"{wave_medium} iH"


def test_emoji_zwj_family():
    family = "\U0001F468\u200D\U0001F469\u200D\U0001F467"  # 👨‍👩‍👧
    assert reverse_text(f"A{family}B") == f"B{family}A"
    assert reverse_text(family) == family


def test_emoji_zwj_profession():
    technologist = "\U0001F9D1\u200D\U0001F4BB"  # 🧑‍💻
    assert reverse_text(f"x{technologist}y") == f"y{technologist}x"


def test_regional_indicator_flags():
    us = "\U0001F1FA\U0001F1F8"  # 🇺🇸
    fr = "\U0001F1EB\U0001F1F7"  # 🇫🇷
    assert reverse_text(us) == us
    assert reverse_text(us + fr) == fr + us
    assert reverse_text("go" + us + fr) == fr + us + "og"


def test_flag_with_text():
    us = "\U0001F1FA\U0001F1F8"
    assert reverse_text(f"US{us}") == f"{us}SU"


def test_surrogate_safe_high_emoji():
    s = "ab\U0001F600cd"  # grinning face
    assert reverse_text(s) == "dc\U0001F600ba"


def test_hangul_precomposed_syllable():
    syllable = "\uAC00"  # 가
    assert reverse_text(f"12{syllable}34") == "43" + syllable + "21"


def test_mixed_script():
    assert reverse_text("Hello你好") == "好你olleH"


def test_does_not_mutate_input():
    original = "test"
    reverse_text(original)
    assert original == "test"


def test_cr_lf_preserved():
    # CR+LF is one grapheme cluster per UAX #29 GB2
    assert reverse_text("a\r\nb") == "b\r\na"


def test_variation_selector_stays_with_base():
    heart_vs16 = "\u2764\uFE0F"  # red heart emoji style
    assert reverse_text(f"({heart_vs16})") == f"){heart_vs16}("


@pytest.mark.parametrize(
    "text",
    [
        "",
        "x",
        "\u0301",  # lone combining mark
        "a\u0301b",
    ],
)
def test_roundtrip_length_consistency(text):
    rev = reverse_text(text)
    assert len(list(unicodedata.normalize("NFC", rev))) >= 0
    assert reverse_text(rev) == text


def test_double_reverse_is_identity():
    samples = [
        "The quick brown fox",
        "你好",
        "\U0001F44B\U0001F3FD",
        "\U0001F468\u200D\U0001F469\u200D\U0001F467",
        "\u0065\u0301",
        "\U0001F1FA\U0001F1F8\U0001F1EB\U0001F1F7",
    ]
    for sample in samples:
        assert reverse_text(reverse_text(sample)) == sample
