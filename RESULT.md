# Unicode-aware `reverse_text`

## What was built

`reverse_text(s: str) -> str` in `reverse_text.py` reverses a string by
**extended grapheme cluster**, not by Unicode code point. That keeps
user-perceived characters intact:

| Input | Code-point reverse (`s[::-1]`) | `reverse_text` |
| --- | --- | --- |
| `é` (`e` + U+0301) | accent, then `e` (broken) | `é` |
| `你好` | `好你` | `好你` (same; one code point each) |
| `👋🏻` | skin-tone modifier, then waving hand | `👋🏻` |
| `👨‍👩‍👧‍👦` | split family members and ZWJs | `👨‍👩‍👧‍👦` |
| `a👋🏻b` | `b` + broken emoji + `a` | `b👋🏻a` |

No third-party packages. Segmentation uses the Python standard library
(`bisect`) plus embedded Unicode 15.1 property tables.

## Approach

Naive reversal (`s[::-1]`, or reversing a `list(s)`) walks code points.
Python 3.12’s `unicodedata` has no grapheme iterator (`iter_graphemes`
arrives in 3.15), and `re` has no `\X`, so this module implements
[UAX #29](https://www.unicode.org/reports/tr29/) extended grapheme
cluster boundaries (Unicode 15.1.0) directly.

### Segmentation

The string is scanned left to right. At each boundary between code
points, the rules fire in order until one matches:

- **GB3–GB5** — keep CR+LF together; break around other controls
- **GB6–GB8** — Hangul L/V/T/LV/LVT conjoining
- **GB9 / GB9a** — do not break before Extend (combining marks, skin
  tones, variation selectors, tags) or ZWJ, or before SpacingMark
- **GB9b** — do not break after Prepend
- **GB9c** — Indic conjuncts (`Consonant (Extend|Linker)* Linker
  (Extend|Linker)* × Consonant`)
- **GB11** — emoji ZWJ sequences (`Extended_Pictographic Extend* ZWJ ×
  Extended_Pictographic`)
- **GB12 / GB13** — regional-indicator pairs (flags), paired from the
  start of the run
- **GB999** — otherwise, break

`reverse_text` then joins `reversed(clusters)`.

### Property data

Python’s `unicodedata` does not expose `Grapheme_Cluster_Break`,
`Extended_Pictographic`, or `Indic_Conjunct_Break`. Compact inclusive
ranges from the Unicode 15.1 Character Database are embedded at the
bottom of `reverse_text.py`:

- `GraphemeBreakProperty.txt`
- `emoji-data.txt` (`Extended_Pictographic`)
- `DerivedCoreProperties.txt` (`InCB`)

Hangul syllables U+AC00..U+D7A3 are classified as LV vs LVT in code
(`(cp - 0xAC00) % 28 == 0`) so those 798 ranges are not stored.

Lookups are `bisect` on the sorted start code point, O(log n) per
character.

`grapheme_clusters(s)` is exported for tests and for callers that want
the same split `reverse_text` uses.

## Known limitations

1. **Unicode version.** Tables are Unicode **15.1.0**. Code points that
   first became `Extended_Pictographic` (or gained a new GCB value) in
   Unicode 16–18 may ZWJ-split or otherwise cluster differently until
   the tables are regenerated. All emoji used in the tests, including
   skin tones, families, flags, keycaps, and tag sequences, are covered.

2. **Directional clustering.** UAX #29 is not symmetric.
   `reverse_text(reverse_text(s)) == s` holds for ordinary text (Latin,
   CJK, complete emoji, flag *pairs*). It fails when reversal creates a
   new attachment:
   - **Prepend** binds to the *following* cluster
   - **Extend / ZWJ / SpacingMark** bind to the *previous* cluster
   - **Regional indicators** pair from the left, so three RIs regroup
   - **Hangul jamo** combine in L-V-T order only

3. **No language tailoring.** Default extended graphemes, not
   dictionary-based units. Chinese is reversed per ideograph (the usual
   “character” reverse). Thai/Khmer/etc. use SpacingMark/Prepend rules
   only, not orthographic-syllable tailorings from CLDR.

4. **Logical order, not bidi visual order.** Arabic/Hebrew clusters are
   reversed in logical storage order. A renderer may still display the
   result right-to-left.

5. **No normalization.** NFC `é` (U+00E9) and NFD `e`+U+0301 both
   reverse correctly as clusters, but they remain distinct strings.

6. **Unpaired surrogates** cannot appear in a well-formed Python `str`.

## Tests

`test_reverse_text.py` uses pytest.

- **33 hand-written cases:** empty/ASCII, combining accents (single and
  stacked), precomposed vs decomposed, Chinese (with fullwidth
  punctuation), Japanese, Hangul syllables and jamo, skin-tone emoji,
  ZWJ families and professions, rainbow flag, keycaps, RI flags, England
  tag-sequence flag, VS16, CR/LF, mixed scripts, Devanagari conjuncts,
  round-trip on well-formed text, and the Prepend asymmetry.
- **1185 official cases** from
  [GraphemeBreakTest-15.1.0.txt](https://www.unicode.org/Public/15.1.0/ucd/auxiliary/GraphemeBreakTest.txt),
  encoded as hex cluster specs. Each checks segmentation and that
  `reverse_text` is the cluster list reversed.

Run:

```bash
pip install pytest
python3 -m pytest test_reverse_text.py -q
```

## Test output

Environment: Python 3.12.3, pytest 9.2.0, Linux.

Full suite:

```
........................................................................ [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 35%]
........................................................................ [ 41%]
........................................................................ [ 47%]
........................................................................ [ 53%]
........................................................................ [ 59%]
........................................................................ [ 65%]
........................................................................ [ 70%]
........................................................................ [ 76%]
........................................................................ [ 82%]
........................................................................ [ 88%]
........................................................................ [ 94%]
..................................................................       [100%]
1218 passed in 0.45s
```

Named (non-official) tests:

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /workspace
collecting ... collected 1218 items / 1185 deselected / 33 selected

test_reverse_text.py::test_empty_string PASSED                           [  3%]
test_reverse_text.py::test_single_ascii_character PASSED                 [  6%]
test_reverse_text.py::test_ascii_word PASSED                             [  9%]
test_reverse_text.py::test_ascii_with_spaces_and_punctuation PASSED      [ 12%]
test_reverse_text.py::test_digits_and_symbols PASSED                     [ 15%]
test_reverse_text.py::test_combining_acute_stays_with_base PASSED        [ 18%]
test_reverse_text.py::test_combining_mark_between_letters PASSED         [ 21%]
test_reverse_text.py::test_multiple_combining_marks_on_one_base PASSED   [ 24%]
test_reverse_text.py::test_precomposed_and_decomposed_accented_letters PASSED [ 27%]
test_reverse_text.py::test_combining_enclosing_circle PASSED             [ 30%]
test_reverse_text.py::test_chinese_characters_reverse_per_ideograph PASSED [ 33%]
test_reverse_text.py::test_chinese_with_fullwidth_punctuation PASSED     [ 36%]
test_reverse_text.py::test_japanese_kanji_hiragana_katakana PASSED       [ 39%]
test_reverse_text.py::test_hangul_precomposed_syllables PASSED           [ 42%]
test_reverse_text.py::test_hangul_jamo_conjoin_into_one_cluster PASSED   [ 45%]
test_reverse_text.py::test_emoji_with_skin_tone_modifier PASSED          [ 48%]
test_reverse_text.py::test_two_skin_tone_emoji_reverse_as_units PASSED   [ 51%]
test_reverse_text.py::test_zwj_family_emoji_is_one_cluster PASSED        [ 54%]
test_reverse_text.py::test_two_zwj_sequences_reverse_without_splitting PASSED [ 57%]
test_reverse_text.py::test_zwj_gendered_profession_with_skin_tone PASSED [ 60%]
test_reverse_text.py::test_rainbow_flag_zwj_sequence PASSED              [ 63%]
test_reverse_text.py::test_keycap_emoji PASSED                           [ 66%]
test_reverse_text.py::test_regional_indicator_flag_pair PASSED           [ 69%]
test_reverse_text.py::test_odd_number_of_regional_indicators_pairs_from_the_start PASSED [ 72%]
test_reverse_text.py::test_emoji_tag_sequence_england_flag PASSED        [ 75%]
test_reverse_text.py::test_variation_selector_16_keeps_emoji_presentation PASSED [ 78%]
test_reverse_text.py::test_crlf_is_a_single_cluster PASSED               [ 81%]
test_reverse_text.py::test_lone_lf_and_cr_are_separate PASSED            [ 84%]
test_reverse_text.py::test_mixed_scripts_emoji_and_chinese PASSED        [ 87%]
test_reverse_text.py::test_devanagari_conjunct_ka_virama_ssa PASSED      [ 90%]
test_reverse_text.py::test_zwj_and_skin_tone_do_not_cross_cluster_boundaries PASSED [ 93%]
test_reverse_text.py::test_long_string_round_trip PASSED                 [ 96%]
test_reverse_text.py::test_prepend_makes_round_trip_asymmetric PASSED    [100%]

===================== 33 passed, 1185 deselected in 0.06s ======================
```

**1218 passed, 0 failed.**
