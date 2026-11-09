# Grapheme-cluster string reversal

`reverse_text(s)` reverses a string by **extended grapheme cluster**, the unit Unicode Standard Annex #29 defines for cursor movement and backspace. Emoji with skin tones, ZWJ sequences, combining accents, and Chinese characters each stay intact. The implementation uses only the Python standard library (`bisect`); the Unicode property tables are embedded in `reverse_text.py`.

```text
reverse_text("hello")     -> "olleh"
reverse_text("café")      -> "éfac"
reverse_text("cafe\u0301") -> "e\u0301fac"
reverse_text("a👍🏽b")      -> "b👍🏽a"
reverse_text("你好世界")   -> "界世好你"
reverse_text("👨‍👩‍👧‍👦")  -> "👨‍👩‍👧‍👦"
reverse_text("🇺🇸🇫🇷")     -> "🇫🇷🇺🇸"
reverse_text("a\r\nb")    -> "b\r\na"
```

## Approach

Code-point reversal (`s[::-1]`) walks each Unicode scalar. Several user-perceived characters are stored as more than one scalar:

| Text | Code points | Why it must stay together |
| --- | --- | --- |
| `é` in `cafe\u0301` | U+0065 U+0301 | base + combining acute |
| `👍🏽` | U+1F44D U+1F3FD | emoji + Fitzpatrick modifier (`Extend`) |
| `👨‍👩‍👧‍👦` | four emoji joined by U+200D | GB11 ZWJ sequence |
| `🇺🇸` | U+1F1FA U+1F1F8 | regional-indicator pair (GB12/GB13) |
| `1️⃣` | U+0031 U+FE0F U+20E3 | keycap: base + variation selector + enclosing mark |
| `🏴󠁧󠁢󠁥󠁮󠁧󠁿` | black flag + tag characters | tag sequence (`Extend`) |
| `你好` | U+4F60 U+597D | one cluster each; supplementary ideographs and ideographic variation sequences stay whole too |
| `क्ष` | U+0915 U+094D U+0937 | Indic conjunct (GB9c) |
| `한` as jamo | U+1112 U+1161 U+11AB | Hangul L + V + T (GB6–GB8) |

`reverse_text` splits the string into extended grapheme clusters, reverses that list, and concatenates it. Scalars inside a cluster are copied in their original order. The function does not apply NFC or NFD, so a decomposed accent stays decomposed.

The scanner follows UAX #29 revision 49 (Unicode 18.0.0), extended grapheme clusters, in rule order. The first matching rule decides the boundary:

- **GB3–GB5** keep CR+LF together and break around other controls.
- **GB6–GB8** keep Hangul jamo and precomposed syllables together. LV vs LVT inside U+AC00..U+D7A3 is the standard syllable formula (T-index 0 is LV), checked against `GraphemeBreakProperty.txt`.
- **GB9 / GB9a / GB9b** keep `Extend` (combining marks, skin tones, variation selectors, emoji tags, ZWNJ), `ZWJ`, `SpacingMark`, and `Prepend` with the neighboring base.
- **GB9c** keeps `InCB=Linker` + `InCB=Extend*` + `InCB=Consonant` together (virama conjuncts, including a ZWJ between virama and consonant, because ZWJ is `InCB=Extend`).
- **GB11** keeps `\p{Extended_Pictographic} Extend* ZWJ` × `\p{Extended_Pictographic}` together, which covers family emoji, profession emoji, hair components, and skin tone before the joiner.
- **GB12/GB13** pair regional indicators. An odd number of indicators so far means the next one completes a flag.
- **GB999** breaks everywhere else, which is what splits ordinary Chinese, Latin, and digits one character at a time.

Rules that look behind more than one scalar (GB9c, GB11, GB12/GB13) use a small amount of state carried from the previous code point, so the scan is a single left-to-right pass.

Property values come from the Unicode 18.0.0 Character Database:

- `GraphemeBreakProperty.txt` for `Grapheme_Cluster_Break`
- `emoji-data.txt` for `Extended_Pictographic`
- `DerivedCoreProperties.txt` for `Indic_Conjunct_Break`

Code points missing from those tables use the UCD defaults (`Other`, `InCB=None`, `Extended_Pictographic=No`). This interpreter’s `unicodedata` is Unicode 15.0.0 and does not expose grapheme-break or extended-pictographic values, so the tables are shipped in the module and the result does not depend on the build’s Unicode version.

## Known limitations

These follow from UAX #29, not from a shortcut in the scanner. `test_reverse_text.py` pins the behavior.

- **Logical order.** The function reverses stored characters. It does not run the Unicode Bidirectional Algorithm, so Arabic and Hebrew are reversed in memory order rather than in visual display order.
- **Default clusters, not tailored orthography.** UAX #29 extended grapheme clusters are the default user-perceived characters. They are not language-specific graphemes (Slovak `ch` is two clusters) and they are not font glyphs (an `fi` ligature is two clusters). Some orthographic syllables still break where the standard says to break. Myanmar vowel sign AA after a virama conjunct is its own cluster in the Unicode 18 test suite.
- **ZWNJ and non-emoji ZWJ stick to the preceding cluster.** U+200C is `Extend`, and U+200D is `ZWJ`. GB9 forbids a break before either of them. GB11 glues the *following* character only when both sides are extended pictographic. So `a\u200cb` reverses to `ba\u200c`, and `a\u200db` reverses to `ba\u200d`, while `👩‍💻` stays one cluster.
- **CRLF is one cluster** (GB3). `a\r\nb` reverses to `b\r\na`. A bare LF or CR is its own cluster.
- **Controls block combining marks.** GB4 and GB5 outrank GB9, so a mark after a control is its own cluster: `a\x00\u0301b` reverses to `b\u0301\x00a`.
- **Prepend characters travel with the next cluster.** U+0600 ARABIC NUMBER SIGN + `b` reverses as a unit, ahead of the characters that preceded the prepend.
- **No normalization.** `reverse_text("café")` is `éfac` with precomposed U+00E9. `reverse_text("cafe\u0301")` is `e\u0301fac`. They look the same and compare unequal.
- **Tables are Unicode 18.0.0.** Characters assigned in a later Unicode version are treated as `Other` until the tables are regenerated, which can split a future emoji sequence. Characters this version already encodes, including CJK Extension B and variation selectors through U+E01EF, are covered.
- **Non-RGI emoji.** UTS #51 says every RGI emoji sequence is one grapheme cluster. Some other emoji sequences are several clusters on purpose.
- **Lone surrogates.** Python `str` can hold them. The UCD does not list them, so they use `Grapheme_Cluster_Break=Other`, and a following combining mark attaches. They are not Unicode scalar values.

## Tests

`test_reverse_text.py` covers empty input, ASCII, precomposed and decomposed accents, stacked marks, skin tones, ZWJ families (including skin tone and hair, and the heart-kiss sequence), flags (pairs and a leftover indicator), keycaps, subdivision-flag tags, CJK (BMP, Extension B, ideographic variation sequences, fullwidth letters, punctuation, mixed with emoji), Hangul syllables and jamo, Devanagari conjuncts, spacing marks, prepend, ZWNJ, CRLF, controls, round-trip, and non-`str` input.

It also checks all 853 cases in Unicode 18.0.0 `GraphemeBreakTest.txt` (`testdata/GraphemeBreakTest-18.0.0.txt`): the segmenter must match the published boundaries, and `reverse_text` must equal the reversal of those clusters.

Command:

```text
python3 -m pytest test_reverse_text.py -q --tb=short
```

Output:

```text
........................................................................ [  8%]
........................................................................ [ 16%]
........................................................................ [ 24%]
........................................................................ [ 32%]
........................................................................ [ 40%]
........................................................................ [ 48%]
........................................................................ [ 56%]
........................................................................ [ 64%]
........................................................................ [ 72%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 96%]
................................                                         [100%]
896 passed in 0.38s
```

The 43 hand-written tests, with the 853 conformance cases deselected:

```text
python3 -m pytest test_reverse_text.py -v --tb=line -k 'not conformance'
```

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /workspace
collecting ... collected 896 items / 853 deselected / 43 selected

test_reverse_text.py::test_reversals[-] PASSED                           [  2%]
test_reverse_text.py::test_reversals[a-a] PASSED                         [  4%]
test_reverse_text.py::test_reversals[hello-olleh] PASSED                 [  6%]
test_reverse_text.py::test_reversals[abba-abba] PASSED                   [  9%]
test_reverse_text.py::test_reversals[123-321] PASSED                     [ 11%]
test_reverse_text.py::test_reversals[a b-b a] PASSED                     [ 13%]
test_reverse_text.py::test_reversals[  -  ] PASSED                       [ 16%]
test_reverse_text.py::test_reversals[\u4f60\u597d-\u597d\u4f60] PASSED   [ 18%]
test_reverse_text.py::test_reversals[\u4f60\u597d\u4e16\u754c-\u754c\u4e16\u597d\u4f60] PASSED [ 20%]
test_reverse_text.py::test_reversals[\u4e2d\u6587\uff0c\u6d4b\u8bd5-\u8bd5\u6d4b\uff0c\u6587\u4e2d] PASSED [ 23%]
test_reverse_text.py::test_reversals[\uff21\uff22\uff23-\uff23\uff22\uff21] PASSED [ 25%]
test_reverse_text.py::test_reversals[\u6211\u559c\u6b22\u7f16\u7a0b-\u7a0b\u7f16\u6b22\u559c\u6211] PASSED [ 27%]
test_reverse_text.py::test_reversals[caf\xe9-\xe9fac] PASSED             [ 30%]
test_reverse_text.py::test_reversals[\ud55c\uae00-\uae00\ud55c] PASSED   [ 32%]
test_reverse_text.py::test_reversals[a\nb-b\na] PASSED                   [ 34%]
test_reverse_text.py::test_reversals[a\r\nb-b\r\na] PASSED               [ 37%]
test_reverse_text.py::test_reversals[a\nb\r\nc-c\r\nb\na] PASSED         [ 39%]
test_reverse_text.py::test_decomposed_accent_stays_on_its_base PASSED    [ 41%]
test_reverse_text.py::test_stacked_combining_marks_keep_their_order PASSED [ 44%]
test_reverse_text.py::test_isolated_combining_marks_stay_together PASSED [ 46%]
test_reverse_text.py::test_control_does_not_absorb_a_following_mark PASSED [ 48%]
test_reverse_text.py::test_skin_tone_modifier_stays_on_emoji PASSED      [ 51%]
test_reverse_text.py::test_zwj_sequences_are_single_clusters PASSED      [ 53%]
test_reverse_text.py::test_zwj_internal_order_is_preserved PASSED        [ 55%]
test_reverse_text.py::test_regional_indicator_flags PASSED               [ 58%]
test_reverse_text.py::test_keycap_and_tag_sequence PASSED                [ 60%]
test_reverse_text.py::test_emoji_variation_selector_stays_with_base PASSED [ 62%]
test_reverse_text.py::test_chinese_supplementary_ideograph_and_variation_selector PASSED [ 65%]
test_reverse_text.py::test_chinese_mixed_with_emoji PASSED               [ 67%]
test_reverse_text.py::test_hangul_jamo_syllable_is_one_cluster PASSED    [ 69%]
test_reverse_text.py::test_devanagari_conjunct_moves_as_one_cluster PASSED [ 72%]
test_reverse_text.py::test_spacing_mark_and_prepend PASSED               [ 74%]
test_reverse_text.py::test_zwnj_stays_with_the_preceding_cluster PASSED  [ 76%]
test_reverse_text.py::test_simple_text_matches_code_point_reversal PASSED [ 79%]
test_reverse_text.py::test_round_trip PASSED                             [ 81%]
test_reverse_text.py::test_long_ascii_and_flag_run PASSED                [ 83%]
test_reverse_text.py::test_unassigned_and_surrogate_defaults PASSED      [ 86%]
test_reverse_text.py::test_non_str_raises_type_error[None] PASSED        [ 88%]
test_reverse_text.py::test_non_str_raises_type_error[1] PASSED           [ 90%]
test_reverse_text.py::test_non_str_raises_type_error[hello] PASSED       [ 93%]
test_reverse_text.py::test_non_str_raises_type_error[value3] PASSED      [ 95%]
test_reverse_text.py::test_signature_and_docstring PASSED                [ 97%]
test_reverse_text.py::test_ucd_file_has_the_unicode_18_suite PASSED      [100%]

====================== 43 passed, 853 deselected in 0.05s ======================
```
