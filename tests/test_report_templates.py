import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def markdown_header(path, expected_first_cell):
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] == expected_first_cell:
                return cells
    raise AssertionError(f"No {expected_first_cell!r} table header found in {path}")


def test_benchmark_report_uses_template_stage_columns_and_order():
    assert markdown_header("reports/benchmarks.md", "Stage") == [
        "Stage", "Pages", "s/page p50", "s/page p95", "Peak RSS MB", "Failures", "Notes"
    ]
    content = (ROOT / "reports/benchmarks.md").read_text(encoding="utf-8")
    stages = ["parse_pdfplumber", "tables", "layout", "parse_docling"]
    positions = [content.index(f"| {stage} |") for stage in stages]
    assert positions == sorted(positions)


def test_xbrl_report_uses_template_columns():
    assert markdown_header("reports/xbrl.md", "Path") == [
        "Path", "PDF label", "Concept", "PDF value", "XBRL value", "Status", "Mapping",
        "Diagnosed cause / fix",
    ]


def test_metrics_json_has_exact_suggested_structure():
    metrics = json.loads((ROOT / "reports/metrics.json").read_text(encoding="utf-8"))
    assert list(metrics) == ["text", "tables", "xbrl", "ocr"]
    assert set(metrics["text"]) == {"traditional", "docling"}
    assert all(set(path) == {"wer", "cer", "num_acc"} for path in metrics["text"].values())
    assert set(metrics["tables"]) == {"traditional", "docling"}
    assert all(set(path) == {"precision", "recall", "f1"} for path in metrics["tables"].values())
    assert set(metrics["xbrl"]) == {"traditional", "docling"}
    assert all(set(path) == {"match_rate"} for path in metrics["xbrl"].values())
    assert set(metrics["ocr"]) == {"pages_ocr_share"}
