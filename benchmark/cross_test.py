"""Cross-test the three reverse_text implementations against shared edge cases.

Run from repo root:
    python -m pytest benchmark/cross_test.py -q
or:
    python benchmark/cross_test.py
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES: list[tuple[str, str, str]] = [
    ("empty", "", ""),
    ("ascii", "hello", "olleh"),
    ("chinese", "你好世界", "界世好你"),
    ("accent_nfd", "cafe\u0301", "e\u0301fac"),
    ("accent_nfc", "café", "éfac"),
    ("combining_stack", "a\u0301\u0302b", "ba\u0301\u0302"),
    ("skin_alone", "👋🏻", "👋🏻"),
    ("skin_neighbors", "a👋🏻b", "b👋🏻a"),
    ("family_zwj", "👨‍👩‍👧‍👦", "👨‍👩‍👧‍👦"),
    ("family_neighbors", "x👨‍👩‍👧‍👦y", "y👨‍👩‍👧‍👦x"),
    ("flags", "🇺🇸🇫🇷", "🇫🇷🇺🇸"),
    ("flag_text", "Go🇺🇸!", "!🇺🇸oG"),
    ("keycap", "a1️⃣b", "b1️⃣a"),
    ("hangul_syllable", "한글", "글한"),
    ("hangul_jamo", "\u1112\u1161\u11ab\u1100\u1161", "\u1100\u1161\u1112\u1161\u11ab"),
    ("devanagari", "\u0915\u094d\u0937", "\u0915\u094d\u0937"),
    ("devanagari_neighbors", "a\u0915\u094d\u0937b", "b\u0915\u094d\u0937a"),
    ("crlf", "a\r\nb", "b\r\na"),
    ("england_flag", "a🏴󠁧󠁢󠁥󠁮󠁧󠁿b", "b🏴󠁧󠁢󠁥󠁮󠁧󠁿a"),
    ("mixed_cjk_emoji", "中👍国", "国👍中"),
    ("profession_zwj", "👩‍💻👨", "👨👩‍💻"),
    ("double_reverse_ascii", "Unicode!", "Unicode!"),
]

MODELS = [
    ("composer-2.5", "Composer 2.5", ROOT / "composer-2.5" / "reverse_text.py"),
    ("grok-4.6", "Grok 4.6", ROOT / "grok-4.6" / "reverse_text.py"),
    ("grok-4.7", "Grok 4.7", ROOT / "grok-4.7" / "reverse_text.py"),
]


def load_reverse(path: Path):
    spec = importlib.util.spec_from_file_location(f"rt_{path.parent.name}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.reverse_text


def run() -> dict[str, list[tuple[str, bool, str]]]:
    results: dict[str, list[tuple[str, bool, str]]] = {}
    for key, label, path in MODELS:
        fn = load_reverse(path)
        rows: list[tuple[str, bool, str]] = []
        t0 = time.perf_counter()
        for case_id, inp, expected in CASES:
            try:
                out = fn(fn(inp)) if case_id == "double_reverse_ascii" else fn(inp)
                ok = out == expected
                detail = "" if ok else f"got={out!r} expected={expected!r}"
            except Exception as e:  # noqa: BLE001 — report any failure
                ok = False
                detail = f"EXC {type(e).__name__}: {e}"
            rows.append((case_id, ok, detail))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        passed = sum(1 for _, ok, _ in rows if ok)
        results[key] = rows
        print(f"=== {label}: {passed}/{len(rows)} in {elapsed_ms:.1f}ms ===")
        for case_id, ok, detail in rows:
            mark = "PASS" if ok else "FAIL"
            print(f"  {mark} {case_id}" + (f"  {detail}" if detail else ""))
        print()
    return results


def test_cross_all_models():
    """Pytest entry: every model must be loadable; report failures clearly."""
    results = run()
    # Soft assertion: document scores; hard-fail only if a model crashes entirely
    for key, _, _ in MODELS:
        assert results[key], f"no results for {key}"
        # At least ASCII/empty must pass
        by_id = {cid: ok for cid, ok, _ in results[key]}
        assert by_id["empty"] and by_id["ascii"], f"{key} failed basics"


if __name__ == "__main__":
    results = run()
    print("MATRIX (case x model):")
    print(f"{'case':24} " + " ".join(f"{k:>12}" for k, _, _ in MODELS))
    for i, (case_id, _, _) in enumerate(CASES):
        cells = ["PASS" if results[k][i][1] else "FAIL" for k, _, _ in MODELS]
        print(f"{case_id:24} " + " ".join(f"{c:>12}" for c in cells))
