# Unicode-aware `reverse_text` — results

## Approach

String reversal must respect **user-perceived characters** (extended grapheme clusters), not raw UTF-16/Unicode code units. Reversing by code point would split combining accents from their bases, break emoji ZWJ sequences (e.g. family 👨‍👩‍👧), separate skin-tone modifiers from emoji, and swap the two regional-indicator symbols that form a flag (🇺🇸).

### Algorithm

1. **Segment** the input with a pure-Python implementation of [UAX #29](https://www.unicode.org/reports/tr29/) extended grapheme cluster rules (same model as `unicodedata.iter_graphemes()` in Python 3.15+).
2. **Reverse** the list of cluster substrings and **join** them.

`reverse_text(s)` is therefore `"".join(reversed(clusters))` where each cluster is an element from `_iter_grapheme_clusters(s)`.

### Implementation details

| Concern | Handling |
|--------|----------|
| Combining marks | `GB4` / `GB9`: do not break before `Extend` or `SpacingMark`; `Mn`/`Me` categories treated as extend |
| Emoji + skin tone | Fitzpatrick modifiers (`U+1F3FB–U+1F3FF`) in the Extend table stay attached to the base emoji |
| ZWJ sequences | `GB11`: `Extended_Pictographic Extend* ZWJ × Extended_Pictographic` kept as one cluster |
| Flags | `GB12`/`GB13`: regional indicators pair (`RI RI`) using a trailing-RI count within the current cluster |
| CJK / ASCII | Default cluster boundary (`OTHER`) — one code point per cluster for typical Han/Latin letters |
| Hangul | Jamo composition rules (`GB5`–`GB8`); precomposed syllables (`AC00`–`D7A3`) already single code points |
| CR+LF | `GB2`: `\r\n` kept together |

Unicode property data (Grapheme_Cluster_Break, Extend, Extended_Pictographic, etc.) is embedded as **sorted code-point range tables** and consulted via binary search. Tables are sorted at import time so lookup is correct. Only the **stdlib** (`unicodedata`) is used.

### API

```python
def reverse_text(s: str) -> str:
    ...
```

See `reverse_text.py` for full docstrings.

## Known limitations

1. **Unicode version drift** — Range tables are pinned to a recent Unicode emoji/GCB snapshot. New emoji or rule changes in a future Unicode release may segment differently until tables are updated.
2. **Incomplete UAX #29** — **GB9c** (Indic conjunct clusters / `InCB`) is not implemented; complex Indic syllables built from consonant joiners may split where a full UAX #29 engine would not.
3. **Hangul in Jamo form** — Jamo composition rules apply; most modern Korean text uses precomposed syllables (already one cluster).
4. **No `unicodedata.iter_graphemes` fallback** — Python 3.12 on this environment has no stdlib grapheme iterator; the embedded segmenter is used. On 3.15+, the stdlib implementation could replace the custom segmenter for guaranteed conformance.
5. **Conformance testing** — Tests are hand-picked edge cases, not the full Unicode `GraphemeBreakTest.txt` suite.
6. **Normalization** — Input is not normalized (NFC/NFD); reversal preserves the encoding shape of each cluster (e.g. precomposed vs. decomposed `é` both reverse correctly within their cluster shape).

## Test output

All tests pass with **pytest** (21 cases):

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
collected 21 items

test_reverse_text.py::test_empty_and_ascii PASSED
test_reverse_text.py::test_chinese PASSED
test_reverse_text.py::test_combining_accent_precomposed PASSED
test_reverse_text.py::test_combining_accent_decomposed PASSED
test_reverse_text.py::test_multiple_combining_marks PASSED
test_reverse_text.py::test_emoji_skin_tone PASSED
test_reverse_text.py::test_emoji_zwj_family PASSED
test_reverse_text.py::test_emoji_zwj_profession PASSED
test_reverse_text.py::test_regional_indicator_flags PASSED
test_reverse_text.py::test_flag_with_text PASSED
test_reverse_text.py::test_surrogate_safe_high_emoji PASSED
test_reverse_text.py::test_hangul_precomposed_syllable PASSED
test_reverse_text.py::test_mixed_script PASSED
test_reverse_text.py::test_does_not_mutate_input PASSED
test_reverse_text.py::test_cr_lf_preserved PASSED
test_reverse_text.py::test_variation_selector_stays_with_base PASSED
test_reverse_text.py::test_roundtrip_length_consistency[...] PASSED (4 variants)
test_reverse_text.py::test_double_reverse_is_identity PASSED

============================== 21 passed in 0.03s ==============================
```

Run locally:

```bash
pip install pytest
pytest test_reverse_text.py -v
python -m doctest reverse_text.py -v
```
