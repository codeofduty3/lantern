"""Part 9 - regression tests on the committed fixtures (no network, no DVC remote).

Thresholds live in params.yaml (tests:) and are set from the measured baseline with a margin.
Ground-truth files in tests/fixtures/gt/ follow tests/fixtures/gt/CONVENTIONS.md.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import cell_set, gt_dirs, prf, score_page  # noqa: E402
from managed import cache_path  # noqa: E402
from parse_text import extract_page_text, needs_ocr, page_signals  # noqa: E402
from tables import clean_table, extract_best_df, row_scale, to_number  # noqa: E402

FX = ROOT / "tests" / "fixtures"
GT = FX / "gt"
P = yaml.safe_load((ROOT / "params.yaml").read_text())
T = P["tests"]


def n_pages(pdf):
    with pdfplumber.open(FX / pdf) as p:
        return len(p.pages)


# ---------------------------------------------------------------- OCR routing
def test_scanned_fixture_triggers_ocr_on_every_page():
    with pdfplumber.open(FX / "scanned.pdf") as pdf:
        for page in pdf.pages:
            assert needs_ocr(page_signals(page), P["ocr"])[0], f"page {page.page_number}"


def test_statement_fixture_keeps_text_layer():
    with pdfplumber.open(FX / "statement.pdf") as pdf:
        assert not needs_ocr(page_signals(pdf.pages[0]), P["ocr"])[0]


def test_scanned_fixture_ocr_is_not_empty():
    for n in range(1, n_pages("scanned.pdf") + 1):
        assert len(extract_page_text(FX / "scanned.pdf", n).split()) > 20


# ---------------------------------------------------------------- normalizer
@pytest.mark.parametrize("raw,scale,expected", [
    ("(1,234)", 1e6, -1.234e9), ("—", 1e6, 0.0), ("$ 9,871", 1.0, 9871.0),
    ("1,234(1)", 1.0, 1234.0), ("(5)", 1.0, -5.0), ("12%", 1.0, 12.0), ("Net sales", 1.0, None)])
def test_to_number(raw, scale, expected):
    assert to_number(raw, scale) == expected


def test_row_scale_exceptions():
    cap = "(In millions, except number of shares, which are reflected in thousands, and per-share amounts)"
    assert row_scale("earnings per share", "diluted", "6.08", cap, 1e6) == 1.0
    assert row_scale("shares used in computing earnings per share", "basic", "1", cap, 1e6) == 1e3
    assert row_scale("", "net income", "112,010", cap, 1e6) == 1e6


def test_clean_table_skips_split_date_heading_before_years():
    raw = pd.DataFrame([
        ["", "For the", "Years Ended December", "31,"],
        ["(in thousands, except per share data)", "2024", "2023", "2022"],
        ["Revenue", "$ 3,991,168", "$ 3,811,920", "$ 3,616,654"],
    ])
    tidy, stats = clean_table(raw)
    assert stats["periods"] == 3
    assert tidy[["label", "period", "raw"]].to_dict("records") == [
        {"label": "revenue", "period": "2024", "raw": "$ 3,991,168"},
        {"label": "revenue", "period": "2023", "raw": "$ 3,811,920"},
        {"label": "revenue", "period": "2022", "raw": "$ 3,616,654"},
    ]


def test_managed_cache_key_is_stable_and_page_specific():
    prefix = b"%PDF /ID[<"
    suffix = b"><" + b"0" * 32 + b">] /CreationDate (D:20261007000000) /ModDate (D:20261007000000) "
    first = prefix + b"1" * 32 + suffix + b"page"
    second = prefix + b"2" * 32 + suffix.replace(b"20261007000000", b"20261007000001") + b"page"
    assert cache_path(first) == cache_path(second)
    assert cache_path(first) != cache_path(first + b" changed")


# ---------------------------------------------------------------- text quality vs ground truth
TEXT_PAGES = [("scanned", n, T["max_wer_scanned"]) for n in (1, 2, 3)] + \
             [("statement", 1, T["max_wer_text"]), ("multicol", 1, T["max_wer_text"])]


@pytest.mark.parametrize("stem,page,limit", TEXT_PAGES)
def test_text_wer(stem, page, limit):
    gt = GT / f"{stem}_p{page}.gt.txt"
    if not gt.exists():
        pytest.skip(f"ground truth {gt.name} not transcribed yet")
    hyp = extract_page_text(FX / f"{stem}.pdf", page)
    assert score_page(gt.read_text(), hyp)["wer"] <= limit


# ---------------------------------------------------------------- table quality vs ground truth
def test_statement_cells_f1():
    gt = GT / "statement_p1_t1.gt.csv"
    if not gt.exists():
        pytest.skip("statement table ground truth not transcribed yet")
    gold_df = pd.read_csv(gt, dtype=str).fillna("")
    use_sec = "section" in gold_df.columns
    gold = cell_set(gold_df, use_sec)
    pred = cell_set(extract_best_df(FX / "statement.pdf").astype(str), use_sec)
    assert prf(pred, gold)["f1"] >= T["min_cell_f1"]


# ---------------------------------------------------------------- ground-truth coverage
# The evaluated GT set must not silently shrink: when data/ground_truth is missing
# (PR #5, and again before e131618) evaluate happily scores the CI fixture alone and
# reports table F1 0.95 as if it improved. That number is a coverage regression, not
# a win. CI is deliberately offline with no DVC remote, so the full-set assertion
# only fires where the data is actually present.
def test_ground_truth_coverage():
    assert list(GT.glob("*_t*.gt.csv")), "fixture ground truth missing from tests/fixtures/gt"

    full = ROOT / "data" / "ground_truth"
    if not list(full.glob("*_t*.gt.csv")):
        # smoke.yml is offline with no DVC remote, so the full set cannot exist there.
        # Everywhere else, a missing/empty data/ground_truth is the failure this test
        # exists to catch, so fail loudly rather than skipping past it.
        if os.environ.get("CI"):
            pytest.skip("data/ground_truth is not fetched in CI (offline, no DVC remote)")
        pytest.fail("data/ground_truth is missing or empty - run `dvc pull`. Without it "
                    "evaluate scores only tests/fixtures/gt and reports ~0.95 as if it "
                    "improved, hiding the 188-cell ground-truth set")

    cells = {}
    for d in gt_dirs():
        for g in sorted(d.glob("*_t*.gt.csv")):
            gold = pd.read_csv(g, dtype=str).fillna("")
            cells[g.name] = len(cell_set(gold, "section" in gold.columns))
    assert len(cells) == 3, f"expected 3 ground-truth tables, found {cells}"
    assert sum(cells.values()) == 188, f"expected 188 ground-truth cells, found {cells}"
