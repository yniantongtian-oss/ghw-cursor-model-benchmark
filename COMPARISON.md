# Cursor model benchmark: Unicode-aware `reverse_text`

MLH Global Hack Week: Builders Week — Challenge 2 (Benchmark Cursor’s Models).

## Exact prompt

> Write a Python function `reverse_text(s: str) -> str` that reverses a string correctly for real-world Unicode, including emoji with skin tones and ZWJ sequences, combining accents, and Chinese text, without third-party packages. Put it in `reverse_text.py` with docstrings, add `test_reverse_text.py` (pytest) covering edge cases, run the tests until they pass, and write `RESULT.md` explaining your approach, known limitations, and the test output. Commit everything.

Each run used the same prompt in a Cursor cloud agent on this repository, with a different model selected.

## Models

| # | Model | Agent | Branch / PR |
|---|-------|-------|-------------|
| 1 | **Composer 2.5** | [bc-6fefb544…](https://cursor.com/agents/bc-6fefb544-6745-5422-9935-dc4adce0d6e9) | `cursor/reverse-text-unicode-d6e9` ([PR #1](https://github.com/yniantongtian-oss/ghw-cursor-model-benchmark/pull/1)) |
| 2 | **Grok 4.6** | [bc-a14a2326…](https://cursor.com/agents/bc-a14a2326-b540-577f-a43c-248713226031) | `cursor/unicode-reverse-text-6031` ([PR #2](https://github.com/yniantongtian-oss/ghw-cursor-model-benchmark/pull/2)) |
| 3 | **Grok 4.7** | [bc-8b7224a5…](https://cursor.com/agents/bc-8b7224a5-7e6a-5c27-94f0-81b4693bbaf5) | `cursor/unicode-grapheme-reverse-baf5` ([PR #3](https://github.com/yniantongtian-oss/ghw-cursor-model-benchmark/pull/3)) |

PRs were **not** merged. Copies of each implementation live under `benchmark/<model>/reverse_text.py`.

## Results table

Measured on this box: Python 3.13.5, pytest 9.2.0, `unicodedata` Unicode 15.1.0 (Asia/Singapore).

| Metric | Composer 2.5 | Grok 4.6 | Grok 4.7 |
|--------|-------------:|---------:|---------:|
| Own pytest suite | **21 / 21** in 0.03s | **1218 / 1218** in 0.46s | **896 / 896** in 0.45s |
| Cross-test (22 shared cases) | **18 / 22** | **22 / 22** | **22 / 22** |
| `reverse_text.py` lines | 847 | 1128 | 1490 |
| Unicode tables claimed | “recent” GCB snapshot (no pin); **no GB9c** | **Unicode 15.1.0** + GB9c | **Unicode 18.0.0** + GB9c + official `GraphemeBreakTest` file |
| Conformance corpus | none (hand cases only) | 1185 cases from UCD 15.1 embedded in tests | 853 cases from UCD 18.0 in `testdata/` |
| Readability | Clear API + subset segmenter; lighter docs | Thorough `RESULT.md`, exported `grapheme_clusters` | Clearest limitations section; TypeError on non-`str` |
| Oddities | Treats two Hangul syllables as **one** cluster; splits England tag-flag; no TypeError on `None` | Large inlined UCD tables; TypeError message is generic (`len(None)`) | Largest file (~65 KB tables); ships `testdata/GraphemeBreakTest-18.0.0.txt` |

### Cross-test case matrix

Shared cases include: empty string, ASCII, Chinese, NFC/NFD accents, combining-mark stacks, skin-tone emoji, family ZWJ, flag pairs, keycaps (`1️⃣`), Hangul syllables + jamo, Devanagari conjuncts, CRLF, England tag flag (`🏴󠁧󠁢󠁥󠁮󠁧󠁿`), mixed CJK+emoji, profession ZWJ, and double-reverse identity.

| Case | Composer 2.5 | Grok 4.6 | Grok 4.7 |
|------|:------------:|:--------:|:--------:|
| empty / ascii / chinese | PASS | PASS | PASS |
| accent NFC + NFD / combining stack | PASS | PASS | PASS |
| skin tone / family ZWJ / flags / keycap | PASS | PASS | PASS |
| hangul_syllable (`한글` → `글한`) | **FAIL** | PASS | PASS |
| hangul_jamo | PASS | PASS | PASS |
| devanagari (+ neighbors) | **FAIL** | PASS | PASS |
| crlf / mixed CJK+emoji / profession | PASS | PASS | PASS |
| england_flag (tag sequence) | **FAIL** | PASS | PASS |
| double_reverse_ascii | PASS | PASS | PASS |

Composer’s four failures match gaps it documented (no GB9c) plus two bugs: Hangul LV/LVT syllables incorrectly glued together, and emoji tag sequences reversed code-point-wise inside the flag.

Reproduce:

```bash
python benchmark/cross_test.py
```

## Pros and cons

### Composer 2.5

**Pros**

- Smallest implementation; fastest own-suite wall time.
- Correct on everyday emoji (skin tone, ZWJ family, RI flags, keycaps), CJK ideographs, accents, and CRLF.
- Readable top-level API and docstring examples.

**Cons**

- Incomplete UAX #29: no Indic conjunct rule (GB9c).
- Real bugs on Hangul syllables and England tag-flag sequences.
- Only 21 hand-written tests; no official `GraphemeBreakTest` corpus.
- Does not reject non-`str` input.

### Grok 4.6

**Pros**

- Full UAX #29 rule set including GB9c; Unicode **15.1** tables.
- Strongest own-suite volume (**1218** tests, including 1185 conformance cases).
- Perfect **22/22** on the shared cross-test.
- Exports `grapheme_clusters` for reuse; detailed `RESULT.md`.

**Cons**

- Heavier than Composer (~1.1k LOC) with large embedded tables.
- Tables are one major Unicode version behind Grok 4.7 (15.1 vs 18.0).
- Non-`str` raises a low-level `TypeError` rather than an explicit message.

### Grok 4.7

**Pros**

- Newest tables (**Unicode 18.0.0**) and ships the official break-test file.
- Perfect **22/22** cross-test; clear TypeError for bad types.
- Best written limitations section (bidi, ZWNJ, prepend asymmetry, etc.).
- Own suite **896** passed (43 hand + 853 conformance).

**Cons**

- Largest artifact (~1.5k LOC / ~65 KB) — most of it property tables.
- Slightly fewer total tests than Grok 4.6’s embedded 15.1 suite (different corpus sizes).

## Verdict

All three models produced a working stdlib-only grapheme-cluster reverse from the same prompt, which is already a strong result. **Grok 4.7** is the best overall: newest Unicode data, explicit API hygiene, and a flawless cross-test. **Grok 4.6** is essentially tied on correctness for this suite and brings the densest automated conformance coverage. **Composer 2.5** is the lightest and still handles common emoji/CJK cases, but its Hangul and tag-sequence bugs plus missing GB9c make it the weakest for production Unicode text.

**Recommendation:** prefer **Grok 4.7** (or Grok 4.6) when Unicode correctness matters; use Composer 2.5 when you want a smaller first draft and will add conformance tests yourself.
