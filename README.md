# ghw-cursor-model-benchmark

MLH Global Hack Week: Builders Week — **Challenge 2: Benchmark Cursor’s Models**.

Same prompt, three Cursor cloud-agent runs, three models:

| Model | PR | Cross-test |
|-------|----|------------|
| Composer 2.5 | [#1](https://github.com/yniantongtian-oss/ghw-cursor-model-benchmark/pull/1) | 18/22 |
| Grok 4.6 | [#2](https://github.com/yniantongtian-oss/ghw-cursor-model-benchmark/pull/2) | 22/22 |
| Grok 4.7 | [#3](https://github.com/yniantongtian-oss/ghw-cursor-model-benchmark/pull/3) | 22/22 |

**Verdict:** Grok 4.7 best overall (Unicode 18 tables + clean API); Grok 4.6 close second (largest conformance suite); Composer 2.5 lightest but fails Hangul syllables, Indic conjuncts, and England tag flags.

Full write-up, exact prompt, and results tables: **[COMPARISON.md](./COMPARISON.md)**.

```text
benchmark/
  composer-2.5/reverse_text.py
  grok-4.6/reverse_text.py
  grok-4.7/reverse_text.py
  cross_test.py
```

```bash
pip install pytest
python benchmark/cross_test.py
```

PRs are left open on purpose (not merged) so each model’s original branch stays intact.
