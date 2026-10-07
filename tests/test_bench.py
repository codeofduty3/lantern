import csv
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bench import bench, representative_sample, summarize_stage  # noqa: E402


def test_representative_sample_is_evenly_spaced_and_bounded():
    sample = representative_sample(list(range(1000)), 100)

    assert len(sample) == 100
    assert sample[0] == 0
    assert sample[-1] == 999
    gaps = [right - left for left, right in zip(sample, sample[1:])]
    assert max(gaps) - min(gaps) <= 1


def test_representative_sample_does_not_pad_small_populations():
    pages = list(range(45))

    assert representative_sample(pages, 100) == pages


def test_bench_records_peak_rss_and_separates_empty_from_exceptions(tmp_path):
    def parse(page):
        if page.page_number == 1:
            return ""
        if page.page_number == 2:
            raise ValueError("bad page")
        return "text"

    pages = [
        ("filing", tmp_path / "filing.pdf", SimpleNamespace(page_number=number))
        for number in range(1, 4)
    ]
    output = tmp_path / "bench.csv"

    bench("parse_pdfplumber", parse, pages, output, eligible_pages=3, population_pages=3)

    with output.open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["status"] for row in rows] == [
        "empty",
        "error:ValueError: bad page",
        "ok",
    ]
    assert all(float(row["peak_rss_mb"]) >= float(row["start_rss_mb"]) for row in rows)
    summary = summarize_stage(output)
    assert summary["sampled"] == 3
    assert summary["empty"] == 1
    assert summary["errors"] == 1
    assert summary["runtime"] is None
