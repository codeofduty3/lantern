"""Part 10 - benchmark seconds/page, peak RSS, failures, cold vs warm per stage.

Batch: up to bench.max_pages pages across the rendered filings (50-100 required).
Stages: parse_pdfplumber (text + OCR trigger), tables (hybrid extractor on table pages),
layout (LayoutParser detect; first page = cold start), parse_docling (single-page PDFs through
one warm converter; first page = cold start incl. model load).

Output: data/bench/{stage}.csv, reports/benchmarks.md (generated block)
Usage:  python src/bench.py [--stages parse_pdfplumber tables layout parse_docling]
"""
import argparse
import csv
import os
import platform
import sys
import tempfile
import time
import traceback
from pathlib import Path

import pandas as pd
import pdfplumber
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BENCH, RENDERED, REPORTS, load_params, numbers, page_pdf_bytes, write_report

proc = psutil.Process(os.getpid())
FIELDS = ["stage", "stem", "page", "seconds", "rss_mb", "rss_delta_mb", "output_len", "status",
          "start"]


def bench(stage, fn, pages, out_csv):
    """Deck's harness: time, RSS and failures per page; first page flagged cold."""
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for i, (stem, pdf_path, page) in enumerate(pages):
            rss0 = proc.memory_info().rss
            t0 = time.perf_counter()
            status, n = "ok", 0
            try:
                n = len(fn(pdf_path, page) or "")
                status = "ok" if n else "empty"
            except Exception:
                status = "error:" + traceback.format_exc(limit=1).splitlines()[-1][:80]
            dt = time.perf_counter() - t0
            rss = proc.memory_info().rss
            w.writerow([stage, stem, page.page_number, round(dt, 3), rss // 2**20,
                        (rss - rss0) // 2**20, n, status, "cold" if i == 0 else "warm"])
    print(f"{stage}: {len(pages)} pages -> {out_csv}")


def stage_fns(P):
    from parse_text import needs_ocr, ocr_page, page_signals
    from tables import extract_best

    def text(pdf_path, page):
        txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
        if needs_ocr(page_signals(page, txt), P["ocr"])[0]:
            txt = ocr_page(page, P["ocr"]["dpi"], P["ocr"]["config"])[0]
        return txt

    def tables(pdf_path, page):
        res = extract_best(pdf_path, page, P["tables"])
        return "x" * sum(df.size for df, _, _ in res["tables"])

    state = {}

    def layout(pdf_path, page):
        from layout import detect, load_model
        if "lp" not in state:
            state["lp"] = load_model(P["layout"])  # cold start is counted
        blocks, _ = detect(state["lp"], page, P["layout"]["dpi"], P["layout"]["score_threshold"])
        return "x" * len(blocks)

    def docling(pdf_path, page):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "lantern_docling", Path(__file__).with_name("docling_parse.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        converter = mod.converter
        if "dl" not in state:
            state["dl"] = converter(False, P["docling"]["table_mode"])
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(page_pdf_bytes(pdf_path, page.page_number))
            tmp.flush()
            return state["dl"].convert(tmp.name).document.export_to_markdown()

    return {"parse_pdfplumber": text, "tables": tables, "layout": layout, "parse_docling": docling}


def summary(P):
    rows, specs = [], (f"{platform.platform()}; {platform.processor() or platform.machine()}; "
                       f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads; "
                       f"{psutil.virtual_memory().total / 2**30:.1f} GB RAM; Python "
                       f"{platform.python_version()}")
    per_page = {}
    stage_errors = {}
    for f in sorted(BENCH.glob("*.csv")):
        b = pd.read_csv(f)
        failed = b[b["status"] != "ok"]
        errors = b["status"].astype(str).str.startswith("error:")
        stage_errors[f.stem] = bool(errors.any())
        valid = b[~errors]
        warm = valid[valid["start"] == "warm"]
        cold = b[b["start"] == "cold"]["seconds"]
        non_ok = len(failed)
        if len(warm):
            p50, p95 = warm["seconds"].median(), warm["seconds"].quantile(0.95)
            p50_text, p95_text = f"{p50:.3f}", f"{p95:.3f}"
            if not errors.any():
                per_page[f.stem] = p50
        else:
            p50_text = p95_text = "-"
        cold_note = f"cold first page {cold.iloc[0]:.2f}s" if len(cold) else "cold page missing"
        rows.append(f"| {f.stem} | {len(b)} | {p50_text} | {p95_text} | {b['rss_mb'].max()} | "
                    f"{non_ok} | {cold_note} |")
    bp = P["bench"]
    pages_year = bp["filings_per_year"] * bp["pages_per_filing"]
    traditional = {"parse_pdfplumber", "tables", "layout"}
    traditional_complete = traditional <= set(per_page) and not any(
        stage_errors.get(stage, False) for stage in traditional)
    text_file, table_file = BENCH / "parse_pdfplumber.csv", BENCH / "tables.csv"
    pages = len(pd.read_csv(text_file)) if text_file.exists() else 0
    table_pages = len(pd.read_csv(table_file)) if table_file.exists() else 0
    table_share = table_pages / pages if pages else 0
    traditional_s = (per_page["parse_pdfplumber"] + per_page["layout"] +
                     per_page["tables"] * table_share) if traditional_complete and pages else None
    docling_s = per_page.get("parse_docling")
    docling_complete = docling_s is not None and not stage_errors.get("parse_docling", False)
    cost = ["| path | USD / 1,000 pages | USD / year | assumptions |",
            "|---|---:|---:|---|"]
    for name, seconds in (("traditional stages", traditional_s),
                          ("Docling alternate", docling_s if docling_complete else None)):
        if seconds is None:
            cost.append(f"| {name} on {bp['vm_name']} | unavailable | unavailable | "
                        "incomplete or failed stage measurements |")
            continue
        usd_1k = seconds * 1000 / 3600 * bp["vm_usd_per_hour"]
        assumption = (f"{seconds:.3f} s/page; ${bp['vm_usd_per_hour']}/h; "
                      f"{bp['pages_per_filing']} pages/filing; engineering time excluded")
        if name == "traditional stages":
            assumption += f"; table stage weighted by {table_share:.0%} candidate-page share"
        cost.append(f"| {name} on {bp['vm_name']} | {usd_1k:.2f} | "
                    f"{usd_1k * pages_year / 1000:,.0f} | {assumption} |")
    for k, v in bp["managed_usd_per_1000_pages"].items():
        cost.append(f"| managed: {k} | {v:.2f} | {v * pages_year / 1000:,.0f} | list price, "
                    "first tier (aws.amazon.com/textract/pricing) |")
    runtime = []
    if traditional_s is not None:
        runtime.append(f"traditional {traditional_s * pages_year / 3600:,.1f} h/year")
    if docling_complete:
        runtime.append(f"Docling {docling_s * pages_year / 3600:,.1f} h/year")
    hours = ("Annual sequential runtime estimate: " + "; ".join(runtime) + "."
             if runtime else "Annual runtime estimate unavailable: no complete path benchmark.")
    md = [f"Machine: {specs}\n",
          "| Stage | Pages | s/page p50 | s/page p95 | Peak RSS MB | Empty/errors | Notes |",
          "|---|---|---|---|---|---|---|", *rows, "",
          f"{hours} EDGAR download is capped at 10 requests/s "
          f"(~{bp['filings_per_year'] * 2 / 10 / 60:.1f} min of requests for "
          f"{bp['filings_per_year']:,} filings at ~2 requests each).\n", *cost]
    write_report(REPORTS / "benchmarks.md", "Cost and throughput benchmarks", "\n".join(md),
                 "Bottleneck stages, CPU vs GPU recommendation, concurrency (process pool per "
                 "stage, EDGAR limit), and the crossover volume vs the managed service.")


def main():
    P = load_params()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+",
                    default=["parse_pdfplumber", "tables", "layout", "parse_docling"])
    a = ap.parse_args()
    BENCH.mkdir(parents=True, exist_ok=True)
    fns = stage_fns(P)
    handles, pages = [], []
    for pdf_path in sorted(RENDERED.glob("*.pdf")):
        pdf = pdfplumber.open(pdf_path)
        handles.append(pdf)
        pages += [(pdf_path.stem, pdf_path, p) for p in pdf.pages]
    pages = pages[:P["bench"]["max_pages"]]
    for st in a.stages:
        batch = pages
        if st == "tables":  # only table-candidate pages, as in the stage
            batch = [x for x in pages
                     if len(numbers(x[2].extract_text() or "")) >= P["tables"]["min_numbers"]]
        bench(st, fns[st], batch, BENCH / f"{st}.csv")
    for h in handles:
        h.close()
    summary(P)
    print("-> reports/benchmarks.md")


if __name__ == "__main__":
    main()
