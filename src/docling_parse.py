"""Part 4 - parse_docling stage: Docling as the alternative parsing path.

For every rendered PDF (and the committed fixtures, for evaluation strata):
  {stem}.md, {stem}.json (lossless DoclingDocument), {stem}_p{NNNN}.md (per page, for WER),
  {stem}_t{NNN}.csv (each table, export_to_dataframe), {stem}_t{NNN}.cells.csv (same normalizer
  as the traditional path), {stem}.prov.jsonl (label, page, bbox normalized to top-left points),
  {stem}_{kind}.cells.csv for primary statements, tables_index.csv, timings.csv
Also the original iXBRL HTML of docling.html_stem -> data/docling/html/ and html_vs_pdf.csv
(what rendering changed). Scanned fixtures get Tesseract OCR; rendered PDFs do not need OCR.
"""
import csv
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import pdfplumber

_SRC = str(Path(__file__).resolve().parent)  # src/ last: this file must not shadow
sys.path = [x for x in sys.path if x not in (_SRC, "")] + [_SRC]  # the docling_parse package
from common import (DOCLING, FIXTURES, RENDERED, ROOT, list_pdfs, load_manifest, load_params,
                    statement_kind)
from tables import clean_table, page_caption
sys.path = [x for x in sys.path if x not in (_SRC, "")] + [_SRC]  # again: tables.py re-inserts src/ first


def converter(ocr: bool, mode: str, backend: str = "docling_parse"):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (PdfPipelineOptions, TableFormerMode,
                                                    TesseractCliOcrOptions)
    from docling.document_converter import DocumentConverter, PdfFormatOption
    opts = PdfPipelineOptions(do_ocr=ocr, do_table_structure=True)
    opts.table_structure_options.mode = TableFormerMode.ACCURATE if mode == "accurate" \
        else TableFormerMode.FAST
    if ocr:
        opts.ocr_options = TesseractCliOcrOptions(lang=["eng"], force_full_page_ocr=True)
    # docling_parse (the default backend) segfaults in its native parser on the rasterized
    # scanned fixture on Intel macOS; pypdfium2 reads the same file. See
    # docling.scanned_backend in params.yaml.
    kwargs = {}
    if backend == "pypdfium2":
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        kwargs["backend"] = PyPdfiumDocumentBackend
    fmt = PdfFormatOption(pipeline_options=opts, **kwargs)
    return DocumentConverter(format_options={InputFormat.PDF: fmt})


def table_grid(t, doc) -> pd.DataFrame:
    """Header row(s) + body as one string grid, so the shared cleaner can read the periods."""
    df = t.export_to_dataframe(doc=doc)
    head = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in df.columns]
    return pd.DataFrame([head] + df.astype(str).values.tolist())


def top_left(bbox, page_h):
    b = bbox.to_top_left_origin(page_height=page_h)
    return [round(b.l, 2), round(b.t, 2), round(b.r, 2), round(b.b, 2)]


def export_doc(doc, stem, out, captions, kinds):
    (out / f"{stem}.md").write_text(doc.export_to_markdown(), encoding="utf-8")
    doc.save_as_json(out / f"{stem}.json")
    for n in sorted(doc.pages):
        (out / f"{stem}_p{n:04d}.md").write_text(doc.export_to_markdown(page_no=n),
                                                 encoding="utf-8")
    with open(out / f"{stem}.prov.jsonl", "w", encoding="utf-8") as f:
        for item, _level in doc.iterate_items():
            for pv in getattr(item, "prov", None) or []:
                h = doc.pages[pv.page_no].size.height
                f.write(json.dumps({"label": str(item.label), "page": pv.page_no,
                                    "bbox": top_left(pv.bbox, h), "units": "pt",
                                    "origin": "top-left", "text": getattr(item, "text", None)})
                        + "\n")
    index, tidies = [], {}
    for i, t in enumerate(doc.tables):
        pv = t.prov[0] if t.prov else None
        page = pv.page_no if pv else None
        grid = table_grid(t, doc)
        grid.to_csv(out / f"{stem}_t{i:03d}.csv", index=False, header=False)
        tidy, st = clean_table(grid, captions.get(page, ""))
        tidy.to_csv(out / f"{stem}_t{i:03d}.cells.csv", index=False)
        kind = kinds.get(page)
        index.append({"stem": stem, "table": i, "page": page, "kind": kind or "",
                      "rows": grid.shape[0], "cols": grid.shape[1], "cells": len(tidy),
                      "bbox": top_left(pv.bbox, doc.pages[page].size.height) if pv else None})
        if kind:
            tidies.setdefault(kind, []).append((page, tidy))
    for kind, cands in tidies.items():  # first page of the statement, biggest table on it
        first = min(p for p, _ in cands)
        tidy = max((t for p, t in cands if p == first), key=len)
        tidy.to_csv(out / f"{stem}_{kind}.cells.csv", index=False)
    return index


def page_context(pdf_path):
    """Captions (scale) and statement kinds per page, from the same PDF text layer."""
    caps, kinds = {}, {}
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            caps[p.page_number] = page_caption(p)
            kinds[p.page_number] = statement_kind(p.extract_text() or "")
    return caps, kinds


def main():
    cfg = load_params("docling")
    DOCLING.mkdir(parents=True, exist_ok=True)
    conv, conv_ocr = converter(False, cfg["table_mode"]), None
    timing, index = [], []
    for pdf_path in list_pdfs([RENDERED, FIXTURES]):
        stem = pdf_path.stem
        scanned = stem == "scanned"
        if scanned and conv_ocr is None:
            conv_ocr = converter(True, cfg["table_mode"],
                                 cfg.get("scanned_backend", "pypdfium2"))
        t0 = time.perf_counter()
        doc = (conv_ocr if scanned else conv).convert(str(pdf_path)).document
        secs = time.perf_counter() - t0
        caps, kinds = page_context(pdf_path)
        index += export_doc(doc, stem, DOCLING, caps, kinds)
        timing.append({"stem": stem, "pages": len(doc.pages), "seconds": round(secs, 2),
                       "s_per_page": round(secs / max(len(doc.pages), 1), 3)})
        print(f"{stem}: {len(doc.pages)} pages, {len(doc.tables)} tables, {secs:.1f}s")

    # the original iXBRL HTML of one filing: isolates what rendering changed
    m = load_manifest().get(cfg["html_stem"])
    if m:
        html_out = DOCLING / "html"
        html_out.mkdir(exist_ok=True)
        from docling.document_converter import DocumentConverter
        hdoc = DocumentConverter().convert(str(ROOT / m["source_file"])).document
        (html_out / f"{cfg['html_stem']}.md").write_text(hdoc.export_to_markdown(), encoding="utf-8")
        pdf_tables = [r for r in index if r["stem"] == cfg["html_stem"]]
        rows = []
        for i, t in enumerate(hdoc.tables):
            grid = table_grid(t, hdoc)
            grid.to_csv(html_out / f"{cfg['html_stem']}_t{i:03d}.csv", index=False, header=False)
            tidy, _ = clean_table(grid, "")
            tidy.to_csv(html_out / f"{cfg['html_stem']}_t{i:03d}.cells.csv", index=False)
            rows.append(len(tidy))
        pdf_md = (DOCLING / f"{cfg['html_stem']}.md").read_text(encoding="utf-8")
        html_md = (html_out / f"{cfg['html_stem']}.md").read_text(encoding="utf-8")
        with open(DOCLING / "html_vs_pdf.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "rendered_pdf", "original_html"])
            w.writerow(["tables", len(pdf_tables), len(hdoc.tables)])
            w.writerow(["numeric_cells", sum(r["cells"] for r in pdf_tables), sum(rows)])
            w.writerow(["markdown_chars", len(pdf_md), len(html_md)])
            w.writerow(["pages", next((t["pages"] for t in timing if t["stem"] == cfg["html_stem"]),
                                      ""), "n/a (HTML has no pages)"])
        print(f"html: {len(hdoc.tables)} tables -> {html_out}")

    pd.DataFrame(index).to_csv(DOCLING / "tables_index.csv", index=False)
    with open(DOCLING / "timings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stem", "pages", "seconds", "s_per_page"])
        w.writeheader()
        w.writerows(timing)
    (DOCLING / "version.txt").write_text(f"docling {version('docling')}\n")


if __name__ == "__main__":
    main()
