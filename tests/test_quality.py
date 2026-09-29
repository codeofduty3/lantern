"""Part 9 - regression tests on the committed fixtures (no network, no DVC remote).

Thresholds live in params.yaml (tests:) and are set from the measured baseline with a margin.
Ground-truth files in tests/fixtures/gt/ follow tests/fixtures/gt/CONVENTIONS.md.
"""
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import cell_set, prf, score_page  # noqa: E402
from parse_text import extract_page_text, needs_ocr, page_signals  # noqa: E402
from tables import extract_best_df, row_scale, to_number  # noqa: E402

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
