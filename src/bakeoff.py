"""Part 2 - bake-off on statement pages -> reports/tables_method.md.

Methods: Camelot lattice, stream, network, hybrid and pdfplumber "text", each cleaned with the
same normalizer. Per page: shape, Camelot parsing report, number coverage, placed cells, merged
cells, periods, runtime, and a 10-cell hand check.

Hand check (per page): the first run writes reports/handcheck/{stem}_p{NNNN}.csv with 10 cells;
type each value exactly as printed on the PDF page (read the page, not any CSV), then rerun.

Usage: python src/bakeoff.py                 # income statement + balance sheet of each 10-K
       python src/bakeoff.py --pages 32 34   # explicit pages of the first 10-K
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import camelot
import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (REPORTS, RENDERED, TABLES, find_statement_page, load_params, statement_kind,
                    write_report)
from tables import (clean_table, coverage, norm_label, page_caption, quality, ref_numbers,
                    row_scale, run_flavor, scale_from_caption, to_number, wide)

METHODS = ["lattice", "stream", "network", "hybrid", "pdfplumber"]
HC_DIR = REPORTS / "handcheck"


def run_page(pdf_path, page, cfg):
    ref, cap = ref_numbers(page), page_caption(page)
    out = {}
    for m in METHODS:
        t0 = time.perf_counter()
        try:
            ts = run_flavor(pdf_path, page, m, cfg)
            err = ""
        except Exception as e:
            ts, err = [], f"{type(e).__name__}"
        secs = time.perf_counter() - t0
        if not ts:
            out[m] = {"n": 0, "shape": "-", "acc": None, "ws": None, "cov": 0.0, "cells": 0,
                      "merged": 0, "periods": 0, "sec": secs, "tidy": pd.DataFrame(), "err": err}
            continue
        df, rep, _ = max(ts, key=lambda x: coverage(x[0], ref))  # the statement table
        tidy, st = clean_table(df, cap)
        placed = len(tidy) if st["periods"] else 0
        out[m] = {"n": len(ts), "shape": f"{df.shape[0]}x{df.shape[1]}", "acc": rep.get("accuracy"),
                  "ws": rep.get("whitespace"), "q": round(quality(rep), 1),
                  "cov": coverage(df, ref), "cells": placed, "merged": st["merged_cells"],
                  "periods": st["periods"], "sec": secs, "tidy": tidy, "err": err}
    return out, sum(ref.values()), cap


def hc_path(stem, pno):
    return HC_DIR / f"{stem}_p{pno:04d}.csv"


def make_template(path, tidy):
    """10 cells across rows/periods, preferring negatives, dashes and per-share values."""
    tidy = tidy.reset_index(drop=True)
    tricky = tidy[tidy["raw"].str.contains(r"\(|[\u2013\u2014]|\.\d", regex=True)].head(4)
    rest = tidy.drop(tricky.index)
    step = max(len(rest) // max(10 - len(tricky), 1), 1)
    pick = pd.concat([tricky, rest.iloc[::step]]).head(10)
    t = pick[["section", "label", "period"]].copy()
    t["expected_as_printed"] = ""
    path.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(path, index=False)


def lookup(tidy, section, label, period):
    if tidy.empty:
        return None
    lab = norm_label(label)
    c = tidy[(tidy["period"] == period) & (tidy["label"] == lab)]
    if c.empty:
        c = tidy[(tidy["period"] == period) & tidy["label"].apply(
            lambda s: bool(s) and (s.startswith(lab) or lab.startswith(s)))]
    if len(c) > 1 and section:
        c2 = c[c["section"].str.contains(norm_label(section).split(" ")[0], regex=False)]
        c = c2 if not c2.empty else c
    return None if c.empty else c.iloc[0]


def hand_check(path, res, cap):
    if not path.exists():
        return None
    hc = pd.read_csv(path, dtype=str).fillna("")
    if (hc["expected_as_printed"].str.strip() == "").any():
        return None
    cs = scale_from_caption(cap)
    score, marks = {}, {}
    for m, r in res.items():
        ok = 0
        for i, row in hc.iterrows():
            sc = row_scale(row["section"], row["label"], row["expected_as_printed"], cap, cs)
            exp = to_number(row["expected_as_printed"], sc)
            hit = lookup(r["tidy"], row["section"], row["label"], row["period"])
            good = hit is not None and hit["value"] is not None and exp is not None and \
                abs(hit["value"] - exp) <= 1e-6 * max(1.0, abs(exp))
            ok += good
            marks[(i, m)] = "Y" if good else ("-" if hit is None else f"N({hit['raw']})")
        score[m] = ok
    return score, marks, hc


def f(v, pct=False):
    if v is None or v == "":
        return "-"
    return f"{v:.0%}" if pct else v


def page_section(stem, pno, kind, res, n_ref, cap, hc):
    score = hc[0] if hc else None
    md = [f"### {stem} page {pno} ({kind})\n",
          f"Printed numbers on page (excl. years/footer): {n_ref}; caption scale "
          f"{scale_from_caption(cap):g}.\n",
          "| method | tables | shape | accuracy | whitespace | coverage | placed cells | merged "
          "| periods | sec | hand check (10) |", "|---" * 11 + "|"]
    for m, r in res.items():
        md.append(f"| {m} | {r['n']} | {r['shape']} | {f(r['acc'])} | {f(r['ws'])} | "
                  f"{r['cov']:.0%} | {r['cells']} | {r['merged']} | {r['periods']} | "
                  f"{r['sec']:.1f} | {score[m] if score else 'not filled'} |"
                  + (f" error: {r['err']}" if r['err'] else ""))
    if hc:
        _, marks, t = hc
        md += ["", "Hand check (Y correct, N(raw) wrong value, - cell not found):\n",
               "| section | label | period | printed | " + " | ".join(METHODS) + " |",
               "|---" * (4 + len(METHODS)) + "|"]
        for i, row in t.iterrows():
            md.append(f"| {row['section']} | {row['label']} | {row['period']} | "
                      f"{row['expected_as_printed']} | "
                      + " | ".join(marks[(i, m)] for m in METHODS) + " |")
    else:
        md.append(f"\nHand check pending: fill `{hc_path(stem, pno).relative_to(REPORTS.parent)}` "
                  "and rerun.")
    return md, score


def hybrid_summary():
    log = TABLES / "tables_log.csv"
    if not log.exists():
        return ["Hybrid extractor log not found - run `dvc repro tables` first."]
    with open(log) as fh:
        rows = list(csv.DictReader(fh))
    by = {}
    for r in rows:
        k = (r["kind"] or "other table", r["method"])
        by[k] = by.get(k, 0) + 1
    md = ["| table type | winning method | tables |", "|---|---|---|"]
    md += [f"| {k} | {m} | {n} |" for (k, m), n in sorted(by.items())]
    return md


def main():
    cfg = load_params("tables")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, nargs="*", help="pages of the first 10-K")
    a = ap.parse_args()
    pdfs = sorted(RENDERED.glob("*10K*.pdf")) or sorted(RENDERED.glob("*.pdf"))
    jobs = [(pdfs[0], p) for p in a.pages] if a.pages else []
    for p in ([] if a.pages else pdfs):
        with pdfplumber.open(p) as pdf:
            for kind in ("income_statement", "balance_sheet"):
                n = find_statement_page(pdf, kind=kind)
                if statement_kind(pdf.pages[n - 1].extract_text() or "") == kind:
                    jobs.append((p, n))
    md = [f"Camelot {camelot.__version__}, pdfplumber {pdfplumber.__version__}. Same normalizer "
          "for every method. coverage = share of the page's printed numbers found in the "
          "table; placed = numbers assigned to a (label, period); merged = cells holding 2+ "
          "numbers.\n", "## Bake-off\n"]
    totals = {}
    for pdf_path, pno in jobs:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[pno - 1]
            kind = statement_kind(page.extract_text() or "") or "table"
            res, n_ref, cap = run_page(pdf_path, page, cfg)
            path = hc_path(pdf_path.stem, pno)
            if not path.exists():
                best = max(res, key=lambda m: res[m]["cells"])
                if res[best]["cells"]:
                    make_template(path, res[best]["tidy"])
            hc = hand_check(path, res, cap)
            sec, score = page_section(pdf_path.stem, pno, kind, res, n_ref, cap, hc)
            md += sec + [""]
            for m in METHODS:
                t = totals.setdefault(kind, {}).setdefault(m, [0, 0])
                t[0] += score[m] if score else 0
                t[1] += 10 if score else 0
            print(f"{pdf_path.stem} p{pno} ({kind}): hand check "
                  f"{'scored' if score else 'pending -> ' + str(path)}")
    md += ["## Hand-check accuracy by table type\n",
           "| table type | " + " | ".join(METHODS) + " |", "|---" * (1 + len(METHODS)) + "|"]
    for kind, t in totals.items():
        md.append(f"| {kind} | " + " | ".join(
            f"{t[m][0]}/{t[m][1]}" if t[m][1] else "pending" for m in METHODS) + " |")
    md += ["", "## Hybrid extractor: winning method per table (data/tables/tables_log.csv)\n"]
    md += hybrid_summary()
    write_report(REPORTS / "tables_method.md", "Table extraction: bake-off and method choice",
                 "\n".join(md),
                 "Write 3-5 sentences: preferred method per table type, citing the hand-check "
                 "scores, coverage and merged-cell counts above, and one table where the winner "
                 "loses and why.")
    print("-> reports/tables_method.md")


if __name__ == "__main__":
    main()
