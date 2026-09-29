"""Part 3 - layout stage: LayoutParser block detection, routing, reading order, sections.

Per page: detect Text/Title/List/Table/Figure at layout.dpi, keep score >= score_threshold,
convert pixel boxes to PDF points (top-left). Route:
  Text/Title/List -> pdfplumber text inside the box (Tesseract on the crop if empty)
  Table           -> Part 2 hybrid extractor on the box padded by pad_pt (Camelot table_areas
                     use the bottom-left origin; conversion in tables.to_area)
  Figure          -> crop to data/figures/{stem}_p{NNNN}_b{NNN}.png
Reading order: blocks wider than 60% of the page split the page into bands; inside a band blocks
are clustered into columns by x0 gaps and read column by column, top to bottom. Each block gets
title_section = the nearest preceding Title.

Output: data/layout/{stem}.blocks.jsonl, data/figures/*.png,
        reports/layout/{stem}_p{NNNN}.png (QA overlays), reports/layout_audit.csv/.md
"""
import argparse
import csv
import json
import sys
from importlib.metadata import version
from pathlib import Path

import pdfplumber
from PIL import ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (FIGURES, LAYOUT, RENDERED, REPORTS, FIXTURES, list_pdfs, load_manifest,
                    load_params, numbers, statement_kind, write_report)
from parse_text import ocr_image
from tables import clean_table, extract_best, page_caption, scale_from_caption

COLORS = {"Text": "blue", "Title": "red", "List": "green", "Table": "orange", "Figure": "purple"}
CLASSES = list(COLORS)
AUDIT_CSV = REPORTS / "layout_audit.csv"


def load_model(name):
    import layoutparser as lp
    return lp.AutoLayoutModel(name)


def detect(model, page, dpi, thr):
    import numpy as np
    img = page.to_image(resolution=dpi).original.convert("RGB")
    k = 72 / dpi
    out = []
    for b in model.detect(np.array(img)):
        if float(b.score) < thr:
            continue
        x1, y1, x2, y2 = b.coordinates
        bbox = [max(0.0, x1 * k), max(0.0, y1 * k), min(float(page.width), x2 * k),
                min(float(page.height), y2 * k)]
        out.append({"block_type": str(b.type), "score": round(float(b.score), 3), "bbox": bbox})
    return out, img


def reading_order(blocks, page_w):
    """Bands split by full-width blocks; columns inside a band by x0 gaps; top-down."""
    blocks = sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
    ordered, band = [], []

    def flush():
        if not band:
            return
        xs = sorted(band, key=lambda b: b["bbox"][0])
        col, cols, last = 0, {}, None
        for b in xs:
            if last is not None and b["bbox"][0] - last > 0.2 * page_w:
                col += 1
            cols[id(b)], last = col, b["bbox"][0]
        ordered.extend(sorted(band, key=lambda b: (cols[id(b)], b["bbox"][1])))
        band.clear()

    for b in blocks:
        if b["bbox"][2] - b["bbox"][0] > 0.6 * page_w:
            flush()
            ordered.append(b)
        else:
            band.append(b)
    flush()
    return ordered


def pad(bbox, p, page):
    return [max(0.0, bbox[0] - p), max(0.0, bbox[1] - p),
            min(float(page.width), bbox[2] + p), min(float(page.height), bbox[3] + p)]


def route(b, page, pdf_path, stem, idx, cfg, ocfg, tcfg, versions):
    """Fill text/table/figure content for one block."""
    rec = {"text": None, "table": None, "ocr": False, "ocr_conf": None, "figure_path": None}
    t = b["block_type"]
    if t == "Table":
        box = pad(b["bbox"], cfg["pad_pt"], page)
        res = extract_best(pdf_path, page, tcfg, bbox=box)
        if res["tables"]:
            df, rep, _ = max(res["tables"], key=lambda x: x[0].size)
            cap = page_caption(page)
            tidy, _ = clean_table(df, cap)
            periods = list(dict.fromkeys(tidy["period"]))
            rows = {}
            for r in tidy.itertuples():
                rows.setdefault((r.section, r.label), {})[r.period] = r.value
            rec["table"] = {"columns": ["section", "label"] + periods,
                            "rows": [[k[0], k[1]] + [v.get(p) for p in periods]
                                     for k, v in rows.items()],
                            "raw_cells": df.astype(str).values.tolist(),
                            "scale": scale_from_caption(cap), "padded_bbox": box}
            rec["extractor"] = f"camelot-{res['method']}" if res["method"] != "pdfplumber" \
                else "pdfplumber-table"
            rec["extractor_version"] = versions["camelot"] if res["method"] != "pdfplumber" \
                else versions["pdfplumber"]
            return rec
        t = "Text"  # no table found in the box: keep its text
    if t == "Figure":
        FIGURES.mkdir(parents=True, exist_ok=True)
        fp = FIGURES / f"{stem}_p{page.page_number:04d}_b{idx:03d}.png"
        page.crop(b["bbox"]).to_image(resolution=150).save(fp)
        rec.update(figure_path=str(fp.relative_to(FIGURES.parents[1])),
                   extractor="layoutparser-crop", extractor_version=versions["layoutparser"])
        return rec
    txt = (page.crop(b["bbox"]).extract_text() or "").strip()
    rec.update(extractor="pdfplumber", extractor_version=versions["pdfplumber"])
    if not txt:  # scanned or image text: OCR the crop
        img = page.crop(b["bbox"]).to_image(resolution=ocfg["dpi"]).original
        txt, _, conf = ocr_image(img, ocfg["dpi"], ocfg["config"], offset=b["bbox"][:2])
        rec.update(ocr=True, ocr_conf=round(conf, 1), extractor="tesseract",
                   extractor_version=versions["tesseract"])
    rec["text"] = txt
    return rec


def qa_image(img, blocks, dpi, path):
    k = dpi / 72
    d = ImageDraw.Draw(img)
    for i, b in enumerate(blocks):
        x0, y0, x1, y1 = (v * k for v in b["bbox"])
        c = COLORS.get(b["block_type"], "black")
        d.rectangle([x0, y0, x1, y1], outline=c, width=3)
        d.text((x0 + 3, y0 + 2), f"{i} {b['block_type']} {b['score']:.2f}", fill=c)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def audit_pages(pdf):
    """10 pages: 3 prose, 3 statements, 2 dense notes, 2 cover/exhibit."""
    info = []
    for p in pdf.pages:
        txt = p.extract_text() or ""
        w = len(txt.split())
        info.append((p.page_number, statement_kind(txt), len(numbers(txt)) / max(w, 1), w))
    stm = [i[0] for i in info if i[1]][:3]
    prose = [i[0] for i in sorted(info, key=lambda i: i[2]) if i[3] > 300 and i[0] not in stm][:3]
    notes = [i[0] for i in sorted(info, key=lambda i: -i[2] * i[3])
             if not i[1] and i[0] not in prose][:2]
    edge = [1, len(pdf.pages)]
    strata = [(p, "prose") for p in prose] + [(p, "statement") for p in stm] + \
             [(p, "notes") for p in notes] + [(p, "cover/exhibit") for p in edge]
    return strata[:10]


def update_audit(detected):
    """Write the audit template once; summarise whatever the team has filled in."""
    if not AUDIT_CSV.exists():
        with open(AUDIT_CSV, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["stem", "page", "stratum", "class", "detected", "correct", "missed",
                        "wrong_type"])
            for (stem, page, stratum), counts in detected.items():
                for c in CLASSES:
                    w.writerow([stem, page, stratum, c, counts.get(c, 0), "", "", ""])
    with open(AUDIT_CSV) as f:
        rows = list(csv.DictReader(f))
    filled = [r for r in rows if r["correct"] != ""]
    md = ["Audit sheet: `reports/layout_audit.csv` (team fills correct / missed / wrong_type "
          "per page and class by looking at the QA overlays).\n",
          "| class | detected | correct | missed | wrong type | precision | recall |",
          "|---|---|---|---|---|---|---|"]
    for c in CLASSES:
        rs = [r for r in filled if r["class"] == c]
        det = sum(int(r["detected"]) for r in rs)
        cor = sum(int(r["correct"] or 0) for r in rs)
        mis = sum(int(r["missed"] or 0) for r in rs)
        wro = sum(int(r["wrong_type"] or 0) for r in rs)
        p = f"{cor / det:.2f}" if det else "-"
        r_ = f"{cor / (cor + mis):.2f}" if cor + mis else "-"
        md.append(f"| {c} | {det} | {cor} | {mis} | {wro} | {p} | {r_} |")
    md.append(f"\nPages audited: {len({(r['stem'], r['page']) for r in filled})} / "
              f"{len({(r['stem'], r['page']) for r in rows})}.")
    write_report(REPORTS / "layout_audit.md", "Layout detector audit", "\n".join(md),
                 "Which class is weakest on SEC filings, and one example page.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, nargs="+", default=[RENDERED, FIXTURES])
    ap.add_argument("--out", type=Path, default=LAYOUT)
    a = ap.parse_args()
    P = load_params()
    cfg, ocfg, tcfg = P["layout"], P["ocr"], P["tables"]
    model = load_model(cfg["model"])
    import pytesseract
    versions = {"layoutparser": f"layoutparser {version('layoutparser')}",
                "pdfplumber": f"pdfplumber {version('pdfplumber')}",
                "camelot": f"camelot {version('camelot-py')}",
                "tesseract": f"tesseract {pytesseract.get_tesseract_version()}"}
    manifest = load_manifest()
    a.out.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)  # DVC output must exist even with no figures
    detected, qa_done = {}, 0
    for pdf_path in list_pdfs(a.input):
        stem = pdf_path.stem
        doc_id = manifest.get(stem, {}).get("accession", stem)
        with pdfplumber.open(pdf_path) as pdf, \
                open(a.out / f"{stem}.blocks.jsonl", "w", encoding="utf-8") as fo:
            audit = dict(audit_pages(pdf)) if "10K" in stem else {}
            for page in pdf.pages:
                blocks, img = detect(model, page, cfg["dpi"], cfg["score_threshold"])
                fallback = not blocks
                if fallback:  # detector saw nothing: keep the page as one Text block
                    blocks = [{"block_type": "Text", "score": 0.0,
                               "bbox": [0.0, 0.0, float(page.width), float(page.height)]}]
                blocks = reading_order(blocks, float(page.width))
                section = None
                for i, b in enumerate(blocks, 1):
                    rec = route(b, page, pdf_path, stem, i, cfg, ocfg, tcfg, versions)
                    if b["block_type"] == "Title" and rec["text"]:
                        section = rec["text"].splitlines()[0][:120]
                    fo.write(json.dumps({
                        "doc_id": doc_id, "stem": stem, "page": page.page_number,
                        "block_id": f"p{page.page_number:04d}_b{i:03d}", "order": i,
                        "block_type": b["block_type"], "score": b["score"],
                        "model": "fallback-full-page" if fallback else cfg["model"],
                        "bbox": [round(v, 2) for v in b["bbox"]], "units": "pt",
                        "origin": "top-left", "title_section": section, **rec}) + "\n")
                if page.page_number in audit:
                    counts = {}
                    for b in blocks:
                        counts[b["block_type"]] = counts.get(b["block_type"], 0) + 1
                    detected[(stem, page.page_number, audit[page.page_number])] = counts
                want_qa = page.page_number in audit or stem == "multicol"
                if want_qa and (qa_done < cfg["qa_pages"] or stem == "multicol"):
                    qa_image(img, blocks, cfg["dpi"],
                             REPORTS / "layout" / f"{stem}_p{page.page_number:04d}.png")
                    qa_done += 1
        print(f"{stem}: blocks -> {a.out / (stem + '.blocks.jsonl')}")
    if detected:
        update_audit(detected)


if __name__ == "__main__":
    main()
