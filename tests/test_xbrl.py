import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import xbrl  # noqa: E402
from tables import clean_table  # noqa: E402


def _fact(concept, end, value):
    return {
        "concept": concept,
        "dims": "",
        "instant": True,
        "end": pd.Timestamp(end),
        "days": 0,
        "value": value,
        "decimals": -3,
    }


def test_select_candidate_uses_values_to_disambiguate_duplicate_labels():
    facts = pd.DataFrame([
        _fact("OperatingLeaseLiabilityCurrent", "2025-09-30", 281_347_000),
        _fact("OperatingLeaseLiabilityNoncurrent", "2025-09-30", 846_619_000),
        _fact("OperatingLeaseLiabilityCurrent", "2024-12-31", 259_134_000),
        _fact("OperatingLeaseLiabilityNoncurrent", "2024-12-31", 829_660_000),
    ])
    cells = pd.DataFrame([
        {"period": "2025", "value": 846_619_000, "raw": "846,619"},
        {"period": "2024", "value": 829_660_000, "raw": "829,660"},
    ])

    assert xbrl.select_candidate(
        [("OperatingLeaseLiabilityCurrent", "label"),
         ("OperatingLeaseLiabilityNoncurrent", "label")],
        facts, cells, "balance_sheet", ["2025", "2024"], "10-Q",
    ) == ("OperatingLeaseLiabilityNoncurrent", "label")


def test_select_candidate_keeps_curated_mapping_when_alternate_matches():
    facts = pd.DataFrame([
        _fact("CuratedConcept", "2025-09-30", 280_000_000),
        _fact("AlternateConcept", "2025-09-30", 846_619_000),
    ])
    cells = pd.DataFrame([
        {"period": "2025", "value": 846_619_000, "raw": "846,619"},
    ])

    assert xbrl.select_candidate(
        [("CuratedConcept", "manual"), ("AlternateConcept", "label")],
        facts, cells, "balance_sheet", ["2025"], "10-Q",
    ) == ("CuratedConcept", "manual")


def test_stock_caption_fragments_are_identified_after_ocr_spacing():
    assert xbrl.is_share_caption_fragment("at december 31, 2023")
    assert xbrl.is_share_caption_fragment("outstandin g at d ecember 31, 20")
    assert not xbrl.is_share_caption_fragment("common stock, $0.01 par value")


def test_common_stock_share_count_is_not_compared_as_dollars():
    label = ("common stock, $0.01 par value; 700,000,000 shares authorized; "
             "159,113,000 shares issued and")

    assert xbrl.is_share_count_in_common_stock_value(
        label, 1_437_674_000, 1_591_000, "CommonStockValue")
    assert not xbrl.is_share_count_in_common_stock_value(
        label, 1_591_000, 1_591_000, "CommonStockValue")


def test_clean_table_keeps_common_stock_values_in_period_columns():
    raw = pd.DataFrame([
        ["", "", "", "", "", "", "September 30, 2025", "December 31, 2024"],
        ["", "", "", "", "", "", "2025", "2024"],
        ["Common stock, $0.01 par value; 700,000,000 shares authorized;",
         "159,113,000 shares issued", "", "", "", "", "", ""],
        ["143,767,400", "shares outstanding at September 30, 2025 and "
         "155,647,988 shares issued and 150,025,096", "", "", "", "", "", ""],
        ["", "outstanding at December 31, 2024", "", "", "", "", "1,591", "1,556"],
    ])

    tidy, _ = clean_table(raw, "(in thousands, except shares)")

    assert tidy[["label", "period", "raw", "value"]].to_dict("records") == [
        {"label": "common stock, $0.01 par value", "period": "2025",
         "raw": "1,591", "value": 1_591_000.0},
        {"label": "common stock, $0.01 par value", "period": "2024",
         "raw": "1,556", "value": 1_556_000.0},
    ]


def test_report_includes_match_rate_and_nonmatch_diagnosis(tmp_path, monkeypatch):
    monkeypatch.setattr(xbrl, "REPORTS", tmp_path)
    cmp = pd.DataFrame([
        {"stem": "AKAM", "path": "traditional", "statement": "income_statement",
         "label": "interest expense", "period": "2025", "concept": "InterestExpense",
         "pdf_value": -12, "xbrl_value": 12, "status": "sign", "method": "manual",
         "diagnosis": xbrl.diagnose("sign", "interest expense", "InterestExpense",
                                    "(12)", -12, 12)},
        {"stem": "AKAM", "path": "traditional", "statement": "income_statement",
         "label": "outstanding at december 31", "period": "2025", "concept": "",
         "pdf_value": 2, "xbrl_value": None, "status": "excluded_metadata",
         "method": "excluded",
         "diagnosis": "Share caption fragment; excluded from rate."},
        {"stem": "AKAM", "path": "docling", "statement": "balance_sheet",
         "status": "no_table",
         "diagnosis": "No balance sheet table was generated for this path."},
    ])

    xbrl.report(cmp)
    report = (tmp_path / "xbrl.md").read_text()

    assert "0.0%" in report
    assert "Excluded caption fragments" in report
    assert "Presentation sign convention" in report
    assert "Excluded stock-caption fragments" in report
    assert "No balance sheet table was generated" in report
