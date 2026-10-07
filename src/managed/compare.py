"""Part 7 - send <= managed.max_pages pages through Textract, map into the schema, compare.

Pages: the 10-K income statement page (clean) and the statement page of the scanned fixture.
Run once with credentials:  python src/managed/compare.py --call-api   (then: dvc add data/managed)
Later runs read the cache only (no credentials needed).

Output: reports/managed/{name}.jsonl (schema-validated), {name}_cells.csv and
        {name}_text.txt (side by side), reports/build_vs_buy.md (generated block)
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (FIXTURE_GT, FIXTURES, GROUND_TRUTH, REPORTS, RENDERED, find_statement_page,
                    load_manifest, load_params, rel, sha256, write_report)
from evaluate import score_page
from export import dei_facts
from managed import analyze_page
from managed.textract import lines, mean_conf, tables, text
from parse_text import needs_ocr, ocr_page, page_signals
from schema import write_jsonl
from tables import clean_table, extract_best, page_caption

OUT = REPORTS / "managed"


def open_source(pdf_path, page, P):
    txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
    text_engine = "pdfplumber"
    if needs_ocr(page_signals(page, txt), P["ocr"])[0]:
        txt = ocr_page(page, P["ocr"]["dpi"], P["ocr"]["config"])[0]
        text_engine = "tesseract"
    res = extract_best(pdf_path, page, P["tables"])
    tidy = max((clean_table(df, page_caption(page))[0] for df, _, _ in res["tables"]),
               key=len, default=pd.DataFrame(columns=["section", "label", "period", "raw"]))
    return txt, tidy, res["method"], text_engine


def ground_truth(stem, pno):
    for d in (GROUND_TRUTH, FIXTURE_GT):
        f = d / f"{stem}_p{pno}.gt.txt"
        if f.exists():
            return f.read_text(encoding="utf-8")
    return None


def to_records(resp, page, m, pdf_path, pno, conf):
    w, h = float(page.width), float(page.height)
    base = {"doc_id": m["accession"], "company": m["company"], "cik": m["cik"],
            "ticker": m["ticker"], "form": m["form"], **dei_facts(m["accession"]), "page": pno,
            "section": None, "extractor": "textract-analyze_document",
            "extractor_version": "AnalyzeDocument TABLES", "ocr": True, "ocr_conf": conf,
            "source_path": rel(pdf_path), "sha256": sha256(pdf_path)}
    recs = [{**base, "block_id": f"p{pno:04d}_m{i:03d}", "block_type": "Text",
             "bbox": l["bbox"], "text": l["text"]} for i, l in enumerate(lines(resp, w, h), 1)]
    for k, df in enumerate(tables(resp), 1):
        tidy, _ = clean_table(df, page_caption(page))
        recs.append({**base, "block_id": f"p{pno:04d}_mt{k}", "block_type": "Table",
                     "bbox": [0.0, 0.0, w, h], "text": None,
                     "table": {"columns": ["section", "label", "period", "value"],
                               "rows": tidy[["section", "label", "period", "value"]].values.tolist(),
                               "raw_cells": df.astype(str).values.tolist(), "scale": 1.0}})
    return recs


def side_by_side(oss, man):
    key = ["section", "label", "period"]
    a = oss[key + ["raw"]].rename(columns={"raw": "open_source"})
    b = man[key + ["raw"]].rename(columns={"raw": "managed"})
    j = a.merge(b, on=key, how="outer")
    j["equal"] = j["open_source"].str.replace(r"[\s$]", "", regex=True) == \
        j["managed"].str.replace(r"[\s$]", "", regex=True)
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--call-api", action="store_true", help="allow Textract calls (credentials)")
    a = ap.parse_args()
    P = load_params()
    mcfg = P["managed"]
    manifest = load_manifest()
    tenk = sorted(RENDERED.glob("*10K*.pdf"))[0]
    with pdfplumber.open(tenk) as pdf:
        is_page = find_statement_page(pdf, kind="income_statement")
    fx = json.loads((FIXTURES / "fixtures.json").read_text())
    scan_p = len(fx["scanned"]["pages"])  # last scanned page = the statement
    jobs = [("clean_statement", tenk, is_page), ("scanned_statement", FIXTURES / "scanned.pdf", scan_p)]
    OUT.mkdir(parents=True, exist_ok=True)
    md = ["| page | source | open-source engine | managed | WER open source | WER managed | "
          "managed-vs-open-source WER | reference | table cells: both equal / differ / "
          "only OSS / only managed |",
          "|---|---|---|---|---:|---:|---:|---|---|"]
    for name, pdf_path, pno in jobs[:mcfg["max_pages"]]:
        resp, src = analyze_page(pdf_path, pno, mcfg, force=a.call_api)
        if resp is None:
            md.append(f"| {name} | {pdf_path.name} p{pno} | - | not cached (run --call-api) "
                      "| - | - | - | - |")
            continue
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[pno - 1]
            oss_txt, oss_tidy, method, text_engine = open_source(pdf_path, page, P)
            conf = mean_conf(resp)
            managed_txt = text(resp)
            (OUT / f"{name}_text.txt").write_text(
                f"=== OPEN SOURCE ({text_engine}; tables={method or 'none'}) ===\n"
                f"{oss_txt}\n\n"
                f"=== TEXTRACT ({src}) ===\n{managed_txt}\n",
                encoding="utf-8")
            write_jsonl(to_records(resp, page, manifest[tenk.stem], pdf_path, pno, conf),
                        OUT / f"{name}.jsonl")
            man_tidy = max((clean_table(df, page_caption(page))[0] for df in tables(resp)),
                           key=len, default=pd.DataFrame(columns=oss_tidy.columns))
        stem = pdf_path.stem
        gt = ground_truth(stem, pno)
        ref, ref_name = (gt, "ground truth") if gt else (None, "pdfplumber text layer")
        if ref is None:
            with pdfplumber.open(pdf_path) as pdf:
                ref = pdf.pages[pno - 1].extract_text() or ""
        w_o = score_page(ref, oss_txt)["wer"] if ref else None
        w_m = score_page(ref, managed_txt)["wer"] if ref else None
        w_pair = score_page(oss_txt, managed_txt)["wer"]
        w_o_display = "-" if w_o is None else round(w_o, 4)
        w_m_display = "-" if w_m is None else round(w_m, 4)
        sbs = side_by_side(oss_tidy, man_tidy)
        sbs.to_csv(OUT / f"{name}_cells.csv", index=False)
        both = sbs.dropna(subset=["open_source", "managed"])
        md.append(f"| {name} | {pdf_path.name} p{pno} | {text_engine}; tables="
                  f"{method or 'none'} | textract ({src}, conf "
                  f"{conf:.1f}) | {w_o_display} | {w_m_display} | {round(w_pair, 4)} | "
                  f"{ref_name} | "
                  f"{int(both['equal'].sum())} / {int((~both['equal']).sum())} / "
                  f"{int(sbs['managed'].isna().sum())} / {int(sbs['open_source'].isna().sum())} |")
    price = P["bench"]["managed_usd_per_1000_pages"]
    pages_year = P["bench"]["filings_per_year"] * P["bench"]["pages_per_filing"]
    table_page = price["textract_tables"] / 1000
    detect_page = price["textract_text"] / 1000
    md += ["", "Text comparison files: `reports/managed/*_text.txt`; table-cell comparisons: "
           "`reports/managed/*_cells.csv`; schema-mapped managed records: "
           "`reports/managed/*.jsonl`.\n",
           f"Public AWS list-price reference: [Amazon Textract pricing]("
           "https://aws.amazon.com/textract/pricing/) (US West/Oregon, first 1M pages/month; "
           "rates vary by Region and volume). `DetectDocumentText` is "
           f"${detect_page:.4f}/page; this pipeline instead calls `AnalyzeDocument(TABLES)` "
           f"at ${table_page:.4f}/page. Do not add the two prices: the table-enabled call "
           "returns text and table blocks in one request.",
           "", "| configured workload | pages / year | estimated USD / year |",
           "|---|---:|---:|",
           f"| `AnalyzeDocument(TABLES)` on every page | {pages_year:,} | "
           f"{table_page * pages_year:,.0f} |",
           "", "Estimate uses the configured volume and the public first-tier US West "
           "reference price; it is not an AWS quote."]
    write_report(REPORTS / "build_vs_buy.md", "Build vs buy: managed document AI", "\n".join(md),
                 "Review data residency, retention, model training use, and client approval "
                 "before enabling calls. Keep the managed path opt-in and use it only for "
                 "low-confidence OCR or low-quality tables; otherwise build and operate the "
                 "open-source extraction path.")
    print("-> reports/build_vs_buy.md")


if __name__ == "__main__":
    main()
