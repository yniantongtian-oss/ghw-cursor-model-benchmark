"""Edge cases and UAX #29 conformance tests for reverse_text."""

from pathlib import Path

import pytest

from reverse_text import _grapheme_clusters, reverse_text

# Sequences whose code points must move together.
FAMILY = "👨‍👩‍👧‍👦"
THUMBS_UP_MEDIUM = "👍🏽"
WOMAN_TECHNOLOGIST = "👩‍💻"
WOMAN_MEDIUM_TECHNOLOGIST = "👩🏽‍💻"
MAN_LIGHT_CURLY_HAIR = "👨🏻‍🦱"
COUPLE_WITH_HEART = "👩‍❤️‍💋‍👨"
FLAG_US = "🇺🇸"
FLAG_FR = "🇫🇷"
FLAG_GB = "🇬🇧"
KEYCAP_ONE = "1\ufe0f\u20e3"
ENGLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"
HANGUL_JAMO_HAN = "\u1112\u1161\u11ab"  # ᄒ + ᅡ + ᆫ
KSHA = "\u0915\u094d\u0937"  # Devanagari KA + VIRAMA + SSA
CJK_EXT_B = "\U00020000"
CJK_WITH_IVS = "\u908a\U000e0101"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", ""),
        ("a", "a"),
        ("hello", "olleh"),
        ("abba", "abba"),
        ("123", "321"),
        ("a b", "b a"),
        ("  ", "  "),
        ("你好", "好你"),
        ("你好世界", "界世好你"),
        ("中文，测试", "试测，文中"),
        ("ＡＢＣ", "ＣＢＡ"),
        ("我喜欢编程", "程编欢喜我"),
        ("café", "éfac"),
        ("한글", "글한"),
        ("a\nb", "b\na"),
        ("a\r\nb", "b\r\na"),
        ("a\nb\r\nc", "c\r\nb\na"),
    ],
)
def test_reversals(source: str, expected: str) -> None:
    assert reverse_text(source) == expected


def test_decomposed_accent_stays_on_its_base() -> None:
    source = "cafe\u0301"
    assert reverse_text(source) == "e\u0301fac"
    assert reverse_text(source) != source[::-1]
    # The decomposed sequence is preserved; it is not rewritten as U+00E9.
    assert "\u00e9" not in reverse_text(source)


def test_stacked_combining_marks_keep_their_order() -> None:
    cluster = "e\u0301\u0327"
    assert reverse_text("x" + cluster) == cluster + "x"
    assert reverse_text(cluster) == cluster
    assert cluster[::-1] != cluster


def test_isolated_combining_marks_stay_together() -> None:
    marks = "\u0301\u0300"
    assert reverse_text(marks) == marks
    assert _grapheme_clusters(marks) == [marks]
    assert reverse_text("\u0301") == "\u0301"


def test_control_does_not_absorb_a_following_mark() -> None:
    assert reverse_text("a\x00\u0301b") == "b\u0301\x00a"


def test_skin_tone_modifier_stays_on_emoji() -> None:
    assert reverse_text(THUMBS_UP_MEDIUM) == THUMBS_UP_MEDIUM
    assert reverse_text("a" + THUMBS_UP_MEDIUM + "b") == "b" + THUMBS_UP_MEDIUM + "a"
    assert THUMBS_UP_MEDIUM[::-1] != THUMBS_UP_MEDIUM
    assert _grapheme_clusters("👍" + THUMBS_UP_MEDIUM) == ["👍", THUMBS_UP_MEDIUM]


def test_zwj_sequences_are_single_clusters() -> None:
    for cluster in (
        FAMILY,
        WOMAN_TECHNOLOGIST,
        WOMAN_MEDIUM_TECHNOLOGIST,
        MAN_LIGHT_CURLY_HAIR,
        COUPLE_WITH_HEART,
    ):
        assert len(cluster) > 1
        assert _grapheme_clusters(cluster) == [cluster]
        assert reverse_text("x" + cluster + "y") == "y" + cluster + "x"
        assert cluster[::-1] != cluster


def test_zwj_internal_order_is_preserved() -> None:
    assert [ord(char) for char in reverse_text("ab" + FAMILY)] == [
        ord(char) for char in FAMILY + "ba"
    ]


def test_regional_indicator_flags() -> None:
    assert reverse_text(FLAG_US) == FLAG_US
    assert reverse_text(FLAG_US + FLAG_FR) == FLAG_FR + FLAG_US
    assert reverse_text(FLAG_US + FLAG_FR + FLAG_GB) == FLAG_GB + FLAG_FR + FLAG_US
    assert (FLAG_US + FLAG_FR)[::-1] != FLAG_FR + FLAG_US
    # Three indicators: one pair, then a single leftover indicator.
    assert reverse_text("🇦🇧🇨") == "🇨🇦🇧"
    assert reverse_text("🇦") == "🇦"


def test_keycap_and_tag_sequence() -> None:
    assert len(KEYCAP_ONE) == 3
    assert reverse_text("a" + KEYCAP_ONE + "b") == "b" + KEYCAP_ONE + "a"
    assert len(ENGLAND) == 7
    assert _grapheme_clusters(ENGLAND) == [ENGLAND]
    assert reverse_text("A" + ENGLAND + "B") == "B" + ENGLAND + "A"


def test_emoji_variation_selector_stays_with_base() -> None:
    heart = "\u2764\ufe0f"
    assert reverse_text("a" + heart + "b") == "b" + heart + "a"
    assert heart[::-1] != heart


def test_chinese_supplementary_ideograph_and_variation_selector() -> None:
    assert reverse_text("前" + CJK_EXT_B + "后") == "后" + CJK_EXT_B + "前"
    assert len(CJK_EXT_B) == 1
    assert reverse_text("a" + CJK_WITH_IVS + "b") == "b" + CJK_WITH_IVS + "a"
    assert len(CJK_WITH_IVS) == 2
    assert CJK_WITH_IVS[::-1] != CJK_WITH_IVS


def test_chinese_mixed_with_emoji() -> None:
    assert reverse_text("你好👍🏽世界") == "界世👍🏽好你"
    assert reverse_text("中🀄文") == "文🀄中"
    parts = [
        "H", "e", "l", "l", "o", " ", "你", "好", THUMBS_UP_MEDIUM, FAMILY,
        " ", "c", "a", "f", "é", "\r\n", "한", "글",
    ]
    assert reverse_text("".join(parts)) == "".join(reversed(parts))


def test_hangul_jamo_syllable_is_one_cluster() -> None:
    assert _grapheme_clusters(HANGUL_JAMO_HAN) == [HANGUL_JAMO_HAN]
    assert reverse_text("a" + HANGUL_JAMO_HAN + "b") == "b" + HANGUL_JAMO_HAN + "a"
    # Precomposed Hangul syllables are single code points, so both reversals agree.
    assert reverse_text("한글") == "한글"[::-1]


def test_devanagari_conjunct_moves_as_one_cluster() -> None:
    assert KSHA == "क्ष"
    assert _grapheme_clusters("a" + KSHA + "b") == ["a", KSHA, "b"]
    assert reverse_text("a" + KSHA + "b") == "b" + KSHA + "a"


def test_spacing_mark_and_prepend() -> None:
    # Thai sara am is a spacing mark and stays with the preceding base.
    assert reverse_text("a\u0e01\u0e33b") == "b\u0e01\u0e33a"
    # U+0600 is Prepend, so it stays with the following cluster.
    assert reverse_text("a\u0600b") == "\u0600ba"


def test_zwnj_stays_with_the_preceding_cluster() -> None:
    # U+200C is Grapheme_Cluster_Break=Extend (UAX #29 GB9).
    assert reverse_text("a\u200cb") == "ba\u200c"


def test_simple_text_matches_code_point_reversal() -> None:
    for source in ("hello", "你好世界", "한글", "123", "ＡＢＣ"):
        assert reverse_text(source) == source[::-1]


def test_round_trip() -> None:
    samples = [
        "",
        "a",
        "hello",
        "café",
        "cafe\u0301",
        "e\u0301\u0327",
        "你好世界👍🏽",
        FAMILY,
        FLAG_US + FLAG_FR + "中文",
        KEYCAP_ONE,
        ENGLAND,
        HANGUL_JAMO_HAN,
        KSHA,
        "a\r\nb\n",
        "a\u200cb\u0600c",
        CJK_WITH_IVS,
        MAN_LIGHT_CURLY_HAIR,
        COUPLE_WITH_HEART,
    ]
    for source in samples:
        assert reverse_text(reverse_text(source)) == source
        assert "".join(_grapheme_clusters(source)) == source


def test_long_ascii_and_flag_run() -> None:
    assert reverse_text("ab" * 2500) == "ba" * 2500
    flags = (FLAG_US + FLAG_FR) * 200
    assert reverse_text(flags) == (FLAG_FR + FLAG_US) * 200


def test_unassigned_and_surrogate_defaults() -> None:
    # Unlisted code points use Grapheme_Cluster_Break=Other.
    assert reverse_text("a\u0378b") == "b\u0378a"
    assert reverse_text("a\ud800b") == "b\ud800a"
    assert reverse_text("x\ud800\u0301y") == "y\ud800\u0301x"


@pytest.mark.parametrize("value", [None, 1, b"hello", ["a", "b"]])
def test_non_str_raises_type_error(value: object) -> None:
    with pytest.raises(TypeError):
        reverse_text(value)  # type: ignore[arg-type]


def test_signature_and_docstring() -> None:
    assert reverse_text.__annotations__["s"] is str
    assert reverse_text.__annotations__["return"] is str
    assert reverse_text.__doc__
    assert "UAX #29" in reverse_text.__doc__ or "grapheme" in reverse_text.__doc__.lower()


def _load_ucd_cases() -> list[tuple[str, list[str]]]:
    """Parse Unicode 18.0.0 GraphemeBreakTest.txt into (text, clusters)."""
    path = Path(__file__).resolve().parent / "testdata" / "GraphemeBreakTest-18.0.0.txt"
    cases: list[tuple[str, list[str]]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        body = raw.split("#", 1)[0].strip()
        if not body:
            continue
        tokens = body.split()
        assert tokens[0] == "÷" and tokens[-1] == "÷", raw
        clusters: list[str] = []
        buffer: list[str] = []
        index = 1
        while index < len(tokens) - 1:
            buffer.append(chr(int(tokens[index], 16)))
            separator = tokens[index + 1]
            index += 2
            if separator == "÷":
                clusters.append("".join(buffer))
                buffer = []
            else:
                assert separator == "×", raw
        assert not buffer
        text = "".join(clusters)
        cases.append((text, clusters))
    return cases


_UCD_CASES = _load_ucd_cases()


def test_ucd_file_has_the_unicode_18_suite() -> None:
    assert len(_UCD_CASES) == 853


@pytest.mark.parametrize(
    ("text", "clusters"),
    _UCD_CASES,
    ids=[f"{index:03d}" for index in range(len(_UCD_CASES))],
)
def test_unicode_18_grapheme_break_conformance(text: str, clusters: list[str]) -> None:
    assert _grapheme_clusters(text) == clusters
    assert reverse_text(text) == "".join(reversed(clusters))
