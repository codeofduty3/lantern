"""Parts 5-6 - export stage: provenance JSONL (validated), section Markdown, TXT baseline.

One record per layout block of each filing (traditional path: LayoutParser routing + Parts 1-2).
doc_id/cik/form/ticker/company come from the manifest; fiscal_year/fiscal_period from the filing's
dei:DocumentFiscalYearFocus / dei:DocumentFiscalPeriodFocus iXBRL facts. section = the current
10-K/10-Q Item heading (e.g. "Item 7. ..."), falling back to the nearest preceding Title.

Output: data/export/{stem}.jsonl, {stem}.md, {stem}.txt, format_sizes.csv
"""
import bisect
import csv
import html
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXPORT, LAYOUT, RAW, RENDERED, load_manifest, rel, sha256
from schema import read_jsonl, write_jsonl

ITEM_RE = re.compile(r"^\s*(?:PART\s+[IV]+\s*[—–-]?\s*)?(Item\s+\d{1,2}[A-C]?\.?)(.*)$", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def dei_facts(accession: str) -> dict:
    """fiscal_year / fiscal_period from the unpacked iXBRL document of this filing."""
    for htm in (RAW / "sec-edgar-filings").rglob(f"{accession}/unpacked/*.htm"):
        doc = htm.read_text(errors="ignore")
        if "ix:header" not in doc:
            continue
        out = {}
        for key in ("DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus"):
            m = re.search(rf'<ix:nonNumeric[^>]*name="dei:{key}"[^>]*>(.*?)</ix:nonNumeric>',
                          doc, re.S)
            if m:
                out[key] = html.unescape(TAG_RE.sub("", m.group(1))).strip()
        return {"fiscal_year": int(out.get("DocumentFiscalYearFocus", 0)),
                "fiscal_period": out.get("DocumentFiscalPeriodFocus", "")}
    raise FileNotFoundError(f"no iXBRL document for {accession}")


def item_heading(b) -> str:
    """Item heading if this block starts one (not the table of contents)."""
    if b["block_type"] not in ("Title", "Text") or not b.get("text"):
        return ""
    lines = [l for l in b["text"].splitlines() if l.strip()]
    if not lines or sum(bool(ITEM_RE.match(l)) for l in lines) > 1:  # TOC lists many Items
        return ""
    m = ITEM_RE.match(lines[0])
    if not m or len(lines) > 4 and b["block_type"] != "Title":
        return ""
    return (m.group(1).rstrip(".") + "." + m.group(2)).strip()[:120]


ITEM_LINE_RE = re.compile(
    r"^\s*(?:PART\s+[IV]+\s*[—–-]?\s*)?(Item\s+\d{1,2}[A-C]?\.)\s*(.*)$", re.I)
TOC_LINE_RE = re.compile(r"\s\d{1,3}$")  # table-of-contents lines end with a page number


def item_marks(pdf_path):
    """(page, top, heading) for every real Item heading in the PDF, in reading order.

    Reads every text line with pdfplumber, so headings the layout model missed are found too.
    Table-of-contents lines (ending in a page number) are skipped.
    """
    import pdfplumber
    marks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for ln in page.extract_text_lines():
                text = ln["text"].replace("\xa0", " ").strip()
                m = ITEM_LINE_RE.match(text)
                if not m or TOC_LINE_RE.search(text) or len(text) > 150:
                    continue
                heading = (m.group(1) + " " + m.group(2)).strip()[:120]
                marks.append((page.page_number, ln["top"], heading))
    marks.sort(key=lambda m: m[:2])
    return marks


def table_obj(t):
    if not t:
        return None
    return {"columns": [str(c) for c in t["columns"]], "rows": t["rows"],
            "raw_cells": [[str(c) for c in r] for r in t["raw_cells"]], "scale": t["scale"]}


def grid_md(raw):
    if not raw:
        return ""
    df = pd.DataFrame(raw[1:], columns=[c or " " for c in raw[0]]) if len(raw) > 1 \
        else pd.DataFrame(raw)
    return df.to_markdown(index=False)


def export_doc(stem, m):
    pdf = RENDERED / f"{stem}.pdf"
    dei = dei_facts(m["accession"])
    base = {"doc_id": m["accession"], "company": m["company"], "cik": m["cik"],
            "ticker": m["ticker"], "form": m["form"], **dei,
            "source_path": rel(pdf), "sha256": sha256(pdf)}
    marks = item_marks(pdf)                      # Item headings from the full page text
    keys = [(p, t) for p, t, _ in marks]
    recs = []
    for b in read_jsonl(LAYOUT / f"{stem}.blocks.jsonl"):
        i = bisect.bisect_right(keys, (b["page"], b["bbox"][1] + 2)) - 1
        item = marks[i][2] if i >= 0 else None   # last Item heading above this block
        recs.append({**base, "page": b["page"], "section": item or b.get("title_section"),
                     "block_id": b["block_id"], "block_type": b["block_type"],
                     "bbox": b["bbox"], "text": b.get("text"), "table": table_obj(b.get("table")),
                     "extractor": b["extractor"], "extractor_version": b["extractor_version"],
                     "ocr": bool(b.get("ocr")), "ocr_conf": b.get("ocr_conf")})
    write_jsonl(recs, EXPORT / f"{stem}.jsonl")  # validates every record

    md, txt, current = [f"# {m['company']} {m['form']} ({m['period']})"], [], object()
    for r in recs:  # already in reading order (Part 3)
        if r["section"] != current:
            current = r["section"]
            md.append(f"\n## {current or 'Front matter'}\n")
            txt.append(f"\n{current or ''}\n")
        src = f"<!-- {r['doc_id']} p{r['page']} {r['block_id']} -->"
        md.append(src)
        if r["block_type"] == "Table" and r["table"]:
            md += [f"<!-- scale {r['table']['scale']:g} -->", grid_md(r["table"]["raw_cells"])]
            txt += [" ".join(c for c in row if c) for row in r["table"]["raw_cells"]]
        elif r["block_type"] == "Title" and r["text"]:
            md.append(f"### {r['text'].strip()}")
            txt.append(r["text"].strip())
        elif r["text"]:
            md.append(r["text"].strip())
            txt.append(r["text"].strip())
    (EXPORT / f"{stem}.md").write_text("\n\n".join(md) + "\n", encoding="utf-8")
    (EXPORT / f"{stem}.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    return len(recs)


def main():
    EXPORT.mkdir(parents=True, exist_ok=True)
    sizes = []
    for stem, m in load_manifest().items():
        n = export_doc(stem, m)
        for ext in ("jsonl", "md", "txt"):
            p = EXPORT / f"{stem}.{ext}"
            chars = len(p.read_text(encoding="utf-8"))
            sizes.append({"stem": stem, "format": ext, "bytes": p.stat().st_size,
                          "chars": chars, "approx_tokens": chars // 4})
        print(f"{stem}: {n} records validated -> data/export/{stem}.jsonl/.md/.txt")
    with open(EXPORT / "format_sizes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stem", "format", "bytes", "chars", "approx_tokens"])
        w.writeheader()
        w.writerows(sizes)


if __name__ == "__main__":
    main()
