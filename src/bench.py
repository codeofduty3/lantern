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
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

import pandas as pd
import pdfplumber
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BENCH, RENDERED, REPORTS, load_params, numbers, page_pdf_bytes, write_report

proc = psutil.Process(os.getpid())
MODEL_STAGES = {"layout", "parse_docling"}
FIELDS = ["stage", "stem", "page", "seconds", "start_rss_mb", "peak_rss_mb",
          "peak_rss_delta_mb", "output_len", "status", "start", "eligible_pages",
          "population_pages"]


class RSSSampler:
    """Sample process RSS while a page is being processed."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active = False
        self._peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        while not self._stop.wait(0.01):
            rss = proc.memory_info().rss
            with self._lock:
                if self._active:
                    self._peak = max(self._peak, rss)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()

    def begin(self):
        start_rss = proc.memory_info().rss
        with self._lock:
            self._peak = start_rss
            self._active = True
        return start_rss

    def end(self):
        end_rss = proc.memory_info().rss
        with self._lock:
            self._peak = max(self._peak, end_rss)
            self._active = False
            return self._peak


def representative_sample(items, limit):
    """Select evenly spaced pages across the available population."""
    if len(items) <= limit:
        return items
    if limit == 1:
        return [items[0]]
    indexes = [round(i * (len(items) - 1) / (limit - 1)) for i in range(limit)]
    return [items[i] for i in indexes]


def bench(stage, fn, pages, out_csv, eligible_pages, population_pages):
    """Time sampled pages, recording status and the sampled process RSS peak."""
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        with RSSSampler() as sampler:
            for i, (stem, pdf_path, page) in enumerate(pages):
                rss0 = sampler.begin()
                t0 = time.perf_counter()
                status, n = "ok", 0
                try:
                    result = fn(pdf_path, page) if stage in {"tables", "parse_docling"} else fn(page)
                    n = len(result or "")
                    status = "ok" if n else "empty"
                except Exception:
                    # Keep measuring later pages while preserving each failure in the CSV.
                    status = "error:" + traceback.format_exc(limit=1).splitlines()[-1][:120]
                dt = time.perf_counter() - t0
                peak_rss = sampler.end()
                if stage in MODEL_STAGES:
                    start = "cold" if i == 0 else "warm"
                else:
                    start = "n/a"
                w.writerow([stage, stem, page.page_number, round(dt, 3),
                            round(rss0 / 2**20), round(peak_rss / 2**20),
                            round(max(0, peak_rss - rss0) / 2**20), n, status, start,
                            eligible_pages, population_pages])
    print(f"{stage}: {len(pages)} pages -> {out_csv}")


def stage_fns(params):
    from parse_text import needs_ocr, ocr_page, page_signals
    from tables import extract_best

    def text(page):
        txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
        if needs_ocr(page_signals(page, txt), params["ocr"])[0]:
            txt = ocr_page(page, params["ocr"]["dpi"], params["ocr"]["config"])[0]
        return txt

    def tables(_pdf_path, page):
        res = extract_best(_pdf_path, page, params["tables"])
        return "x" * sum(df.size for df, _, _ in res["tables"])

    state = {}

    def layout(page):
        from layout import detect, load_model
        if "lp" not in state:
            state["lp"] = load_model(params["layout"])  # cold start is counted
        blocks, _ = detect(state["lp"], page, params["layout"]["dpi"],
                           params["layout"]["score_threshold"])
        return "x" * len(blocks)

    def docling(pdf_path, page):
        if "docling_module" not in state:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "lantern_docling", Path(__file__).with_name("docling_parse.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            state["docling_module"] = mod
        if "dl" not in state:
            state["dl"] = state["docling_module"].converter(
                False, params["docling"]["table_mode"])
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(page_pdf_bytes(pdf_path, page.page_number))
            tmp.flush()
            return state["dl"].convert(tmp.name).document.export_to_markdown()

    return {"parse_pdfplumber": text, "tables": tables, "layout": layout, "parse_docling": docling}


def summarize_stage(csv_path):
    data = pd.read_csv(csv_path)
    if data.empty:
        return None
    missing = set(FIELDS) - set(data.columns)
    if missing:
        raise ValueError(
            f"{csv_path} uses an old benchmark schema; rerun all stages with `python src/bench.py`")
    errors = data["status"].astype(str).str.startswith("error:")
    valid = data[~errors]
    timed = valid[valid["start"] == "warm"] if csv_path.stem in MODEL_STAGES else valid
    p50 = timed["seconds"].median() if len(timed) else None
    p95 = timed["seconds"].quantile(0.95) if len(timed) else None
    cold = data[data["start"] == "cold"]["seconds"]
    notes = (f"cold first page {cold.iloc[0]:.2f}s" if len(cold)
             else "no model cold start")
    if len(data) < 50:
        notes += f"; below 50-page target ({len(data)} sampled)"
    return {
        "stage": csv_path.stem,
        "sampled": len(data),
        "eligible": int(data["eligible_pages"].iloc[0]),
        "population": int(data["population_pages"].iloc[0]),
        "p50": p50,
        "p95": p95,
        "runtime": p50 if not errors.any() and len(data) >= 50 else None,
        "peak_rss": float(data["peak_rss_mb"].max()),
        "empty": int((data["status"] == "empty").sum()),
        "errors": int(errors.sum()),
        "notes": notes,
    }


def machine_specs():
    return (f"{platform.platform()}; {platform.processor() or platform.machine()}; "
            f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads; "
            f"{psutil.virtual_memory().total / 2**30:.1f} GB RAM; Python "
            f"{platform.python_version()}")


def cost_rows(bp, by_stage, table_share):
    pages_year = bp["filings_per_year"] * bp["pages_per_filing"]
    required = {"parse_pdfplumber", "tables", "layout"}
    traditional_s = None
    if required <= by_stage.keys() and table_share and all(
            by_stage[stage]["runtime"] is not None for stage in required):
        traditional_s = (by_stage["parse_pdfplumber"]["runtime"] +
                         by_stage["layout"]["runtime"] +
                         by_stage["tables"]["runtime"] * table_share)
    docling = by_stage.get("parse_docling", {}).get("runtime")
    cost = ["| path | USD / 1,000 pages | USD / year | assumptions |",
            "|---|---:|---:|---|"]
    for name, seconds in (("traditional stages", traditional_s), ("Docling alternate", docling)):
        if seconds is None:
            cost.append(f"| {name} on {bp['vm_name']} | unavailable | unavailable | "
                        "incomplete sample or page exceptions |")
            continue
        cost_1k = seconds * 1000 / 3600 * bp["vm_usd_per_hour"]
        assumptions = (f"{seconds:.3f} s/page; ${bp['vm_usd_per_hour']}/h; "
                       f"{bp['pages_per_filing']} pages/filing; download, render, export, XBRL, "
                       f"engineering, storage and egress excluded; {bp['vm_region']} "
                       f"on-demand price assumption ([EC2 pricing]({bp['vm_price_reference']}))")
        if name == "traditional stages":
            assumptions += f"; tables weighted by {table_share:.1%} candidate-page share"
        cost.append(f"| {name} on {bp['vm_name']} | {cost_1k:.2f} | "
                    f"{cost_1k * pages_year / 1000:,.0f} | {assumptions} |")
    for service, price in bp["managed_usd_per_1000_pages"].items():
        annual = price * pages_year / 1000
        cost.append(f"| managed: {service} | {price:.2f} | {annual:,.0f} | list price, "
                    f"first tier, {bp['managed_region']} "
                    "(https://aws.amazon.com/textract/pricing/) |")
    return cost, traditional_s, docling, pages_year


def recommendations(bp, by_stage, traditional_s, table_share):
    lines = []
    if traditional_s is None:
        lines.append("Bottleneck ranking unavailable until all traditional stages have at least "
                     "50 sampled pages without exceptions.")
    else:
        times = {
            "parse_pdfplumber": by_stage["parse_pdfplumber"]["runtime"],
            "layout": by_stage["layout"]["runtime"],
            "tables (weighted)": by_stage["tables"]["runtime"] * table_share,
        }
        bottleneck = max(times, key=times.get)
        lines.append(f"Measured traditional-path bottleneck: {bottleneck} at "
                     f"{times[bottleneck]:.3f} weighted s/page.")
    if by_stage:
        memory_stage = max(by_stage, key=lambda stage: by_stage[stage]["peak_rss"])
        memory_gb = by_stage[memory_stage]["peak_rss"] / 1024
        cpu_count = bp["vm_vcpus"]
        workers = max(1, min(cpu_count, int(0.7 * bp["vm_ram_gb"] / memory_gb)))
        lines.append(
            f"Hardware/concurrency: CPU-first; no GPU timing was collected. GPU comparison "
            f"assumption is ${bp['gpu_vm_usd_per_hour']}/h, not a measured quote "
            f"([EC2 pricing]({bp['vm_price_reference']})); consider a GPU only if layout is the "
            f"bottleneck and a measured speedup offsets its hourly premium. For the assumed "
            f"{cpu_count}-vCPU/{bp['vm_ram_gb']}-GiB VM, use at most {workers} workers under a "
            f"70% RAM budget, based on the measured {memory_stage} process peak "
            f"({memory_gb:.2f} GiB); benchmark scaling because model weights are duplicated "
            "per worker.")
    lines.append(
        "Download concurrency: enforce a shared EDGAR-wide rate limiter at no more than "
        "10 requests/second ([SEC access guidance](https://www.sec.gov/os/accessing-edgar-data)); "
        "downstream processing may use its own bounded worker pool.")
    if traditional_s is not None:
        lines.append(
            "Managed-service crossover: open-source figures are compute-only; engineering, "
            "storage, and egress are excluded. Solve fixed engineering cost / per-page variable "
            "savings for a break-even volume and compare equivalent service coverage.")
    return lines


def summary(params):
    stage_names = ["parse_pdfplumber", "tables", "layout", "parse_docling"]
    summaries = {path.stem: summarize_stage(path) for path in BENCH.glob("*.csv")}
    stages = [summaries.get(name) for name in stage_names]
    stages = [stage for stage in stages if stage is not None]
    by_stage = {stage["stage"]: stage for stage in stages}
    bp = params["bench"]
    table = by_stage.get("tables")
    table_share = (table["eligible"] / table["population"]
                   if table and table["population"] else 0)
    cost, traditional_s, docling_s, pages_year = cost_rows(bp, by_stage, table_share)
    runtime = []
    if traditional_s is not None:
        runtime.append(f"traditional {traditional_s * pages_year / 3600:,.1f} h/year")
    if docling_s is not None:
        runtime.append(f"Docling {docling_s * pages_year / 3600:,.1f} h/year")
    rows = []
    for name in stage_names:
        stage = summaries.get(name)
        if stage is None:
            rows.append(f"| {name} | 0 | - | - | - | not run | no benchmark CSV |")
            continue
        p50 = f"{stage['p50']:.3f}" if stage["p50"] is not None else "-"
        p95 = f"{stage['p95']:.3f}" if stage["p95"] is not None else "-"
        failures = f"{stage['empty']} empty, {stage['errors']} exceptions"
        notes = stage["notes"]
        if stage["sampled"] < stage["eligible"]:
            notes += f"; {stage['eligible']} eligible candidates in {stage['population']} pages"
        rows.append(f"| {name} | {stage['sampled']} | {p50} | {p95} | "
                    f"{stage['peak_rss']:.0f} | {failures} | {notes} |")
    md = [f"Machine / hardware: {machine_specs()}\n",
          "| Stage | Pages | s/page p50 | s/page p95 | Peak RSS MB | Failures | Notes |",
          "|---|---:|---:|---:|---:|---|---|", *rows, "", *cost, "",
          f"p50/p95 use warm pages for model stages and all non-exception pages otherwise; "
          f"RSS is sampled during each page call. Annual measured-stage sequential runtime: "
          f"{'; '.join(runtime) if runtime else 'incomplete benchmark'}. EDGAR download is "
          f"capped at 10 requests/s (~{bp['filings_per_year'] * 2 / 10 / 60:.1f} min of requests "
          f"for {bp['filings_per_year']:,} filings at ~2 requests each).\n",
          *recommendations(bp, by_stage, traditional_s, table_share)]
    write_report(REPORTS / "benchmarks.md", "Cost and throughput benchmarks", "\n".join(md))


def main():
    params = load_params()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+",
                    default=["parse_pdfplumber", "tables", "layout", "parse_docling"])
    ap.add_argument("--stage-worker", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if not 50 <= params["bench"]["max_pages"] <= 100:
        raise ValueError("bench.max_pages must be between 50 and 100")
    fns = stage_fns(params)
    unknown = set(a.stages) - set(fns)
    if unknown:
        raise ValueError(f"Unknown benchmark stage(s): {', '.join(sorted(unknown))}")
    if not a.stage_worker:
        for stage in a.stages:
            subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--stages", stage,
                 "--stage-worker"],
                check=True)
        summary(params)
        print("-> reports/benchmarks.md")
        return

    BENCH.mkdir(parents=True, exist_ok=True)
    handles, pages = [], []
    for pdf_path in sorted(RENDERED.glob("*.pdf")):
        pdf = pdfplumber.open(pdf_path)
        handles.append(pdf)
        pages += [(pdf_path.stem, pdf_path, p) for p in pdf.pages]
    if not pages:
        raise FileNotFoundError(
            f"No rendered filing pages found in {RENDERED}; run `dvc pull` first")
    candidates = [x for x in pages
                  if len(numbers(x[2].extract_text() or "")) >=
                  params["tables"]["min_numbers"]]
    limit = params["bench"]["max_pages"]
    try:
        for st in a.stages:
            eligible = candidates if st == "tables" else pages
            batch = representative_sample(eligible, limit)
            bench(st, fns[st], batch, BENCH / f"{st}.csv", len(eligible), len(pages))
    finally:
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    main()
