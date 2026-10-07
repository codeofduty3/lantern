"""Part 2 - tables stage: hybrid Camelot/pdfplumber extractor + number normalization.

Hybrid rule per table-candidate page (>= tables.min_numbers numeric tokens):
  1. >= min_rulings ruling lines -> lattice first, else stream first; then fallback_flavors
  2. quality = accuracy - 0.5 * whitespace; coverage = share of the page's (or area's) printed
     numbers present in the table; placement = share placed in a labelled (label, period) cell.
     Accept when quality > accept_score AND coverage, placement >= min_coverage. Guards found in
     the bake-off: lattice scores 100/0 on Apple's underline fragments at 25% coverage, and
     network reads 100% of the numbers but drops the label column.
  3. if nothing is accepted, pdfplumber "text" is a third candidate; then the managed fallback
     (cache/API) when the best quality is below managed_below_score
  4. clean: labels, sections, periods from header dates, lone '$' / ')' cells, scale + row
     exceptions (per-share, share counts, %); raw string kept next to the normalized value

Output (--out, default data/tables):
  {stem}_p{NNNN}_t{k}.raw.csv    extractor grid as-is
  {stem}_p{NNNN}_t{k}.cells.csv  long: section,label,period,raw,value,scale
  {stem}_p{NNNN}_t{k}.clean.csv  wide normalized: section,label,<periods>
  {stem}_{kind}.cells.csv / .clean.csv   first page of each primary statement
  tables_log.csv                 one row per table: winning method, scores, coverage, bbox
"""
import argparse
import csv
import re
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

import camelot
import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RENDERED, TABLES, list_pdfs, load_manifest, load_params, numbers, statement_kind

warnings.filterwarnings("ignore")  # camelot/pdfminer are chatty

# ------------------------------------------------------------------ normalizer (deck)
DASHES = {"", "-", "\u2013", "\u2014"}  # -, en, em
FOOT = re.compile(r"(?<=[\d)])\s*\(\d\)$|\*+$")  # 1,234(1)


def to_number(cell: str, scale: float = 1.0):
    s = cell.strip()
    s = s.replace("$", "").replace(",", "")
    s = FOOT.sub("", s).strip()
    if s in DASHES:
        return 0.0  # policy: dash = nil
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()%").strip()
    try:
        v = float(s)
    except ValueError:
        return None  # label or unparseable
    return (-v if neg else v) * scale


def scale_from_caption(text: str) -> float:
    t = text.lower()
    if "in billions" in t:
        return 1e9
    if "in millions" in t:
        return 1e6
    if "in thousands" in t:
        return 1e3
    return 1.0


def row_scale(section: str, label: str, raw: str, caption: str, cap_scale: float) -> float:
    """Row-level exceptions: %, per-share amounts, share counts."""
    if "%" in raw:
        return 1.0  # percentages are not currency
    t = f"{section} {label}".lower()
    cap = caption.lower()
    if "shares used" in t or t.startswith("number of shares") or "weighted-average shares" in t:
        return 1e3 if ("shares" in cap and "thousands" in cap) else cap_scale
    if "per share" in t or "per-share" in t:
        return 1.0
    return cap_scale


# ------------------------------------------------------------------ cleaner
YEAR = re.compile(r"\b(19|20)\d{2}\b")
YEAR_ONLY = re.compile(r"^(19|20)\d{2}$")
NUMCELL = re.compile(r"^\(?-?\$?\s*\d[\d,]*(\.\d+)?\s*\)?%?(\s*\(\d\)|\*+)?$|^[\u2013\u2014-]$")


def _parts(cell: str):
    return [p for p in re.split(r"\s+", cell.replace("$", " ").replace(" %", "%")) if p]


def is_value(cell: str) -> bool:
    """Numeric cell, possibly several numbers glued together by a merged row/column."""
    ps = _parts(cell)
    return bool(ps) and all(NUMCELL.match(p) for p in ps)


def norm_label(s: str) -> str:
    s = re.sub(r"\(\d\)|\*+", "", s or "").replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"\s+", " ", s).strip().strip(":").strip()
    return s.lower()


def _tidy_cell(c) -> str:
    c = re.sub(r"[ \t]+", " ", str(c)).strip()
    c = re.sub(r"\(\s+", "(", c)
    return re.sub(r"(?<=\d)\s+(\)|%)", r"\1", c)  # '(321 )' -> '(321)', '12 %' -> '12%'


def _merge_row(cells):
    """Drop lone '$', glue lone ')' / '%' onto the previous value cell."""
    out = list(cells)
    for j, c in enumerate(out):
        if c in (")", "%", ")%") and j:
            k = j - 1
            while k >= 0 and not out[k]:
                k -= 1
            if k >= 0:
                out[k] = out[k] + c
            out[j] = ""
        elif c == "$":
            out[j] = ""
    return out


def clean_table(df: pd.DataFrame, caption: str = ""):
    """Extractor DataFrame -> (tidy long DataFrame, stats). Works for any extractor."""
    grid = [[_tidy_cell(c) for c in row] for row in df.fillna("").values]
    grid = [_merge_row(r) for r in grid]
    ncol = max((len(r) for r in grid), default=0)
    stats = {"merged_cells": 0, "periods": 0}

    def row_values(r):  # (col, raw) of value cells, first col is a label if it is a year
        vals = [(j, c) for j, c in enumerate(r) if c and is_value(c)]
        if vals and vals[0][0] == 0 and YEAR_ONLY.match(vals[0][1]) and len(vals) > 1:
            vals = vals[1:]
        return vals

    # A split date heading can contain numeric fragments (e.g. "31,") before
    # the actual year row. Do not mistake those fragments for the first data row.
    first_year_row = next((i for i, r in enumerate(grid)
                           if any(YEAR.search(c) for c in r)), None)
    first_data = next((i for i, r in enumerate(grid)
                       if (first_year_row is None or i > first_year_row)
                       and any(not YEAR_ONLY.match(c) for _, c in row_values(r))), len(grid))
    head, header_end = {}, 0
    for i, r in enumerate(grid[:first_data]):
        for j, c in enumerate(r):
            for y in YEAR.finditer(c):
                head[j] = y.group()
                header_end = i + 1  # label rows after the last year row are data sections
    periods, seen = {}, {}
    for j in sorted(head):  # unique period names (10-Q: 3-month and 9-month columns)
        seen[head[j]] = seen.get(head[j], 0) + 1
        periods[j] = head[j] if seen[head[j]] == 1 else f"{head[j]}_{seen[head[j]]}"
    stats["periods"] = len(periods)

    cap_scale = scale_from_caption(caption)
    recs, section, pending = [], "", None  # pending = label-only row that may continue
    pending_common_stock = False
    for r in grid[header_end:]:
        vals = row_values(r)
        if periods:
            # Numbers in labels/captions (authorized shares, dates) precede the
            # period columns and must not be mistaken for statement amounts.
            first_period_col = min(periods)
            vals = [(j, c) for j, c in vals if j >= first_period_col]
        first_val = vals[0][0] if vals else ncol
        label = " ".join(c for j, c in enumerate(r) if c and j < first_val and not is_value(c))
        label = label.replace("\n", " ").strip()
        if not vals:
            if label:
                if pending is not None:
                    pending_key = re.sub(r"[^a-z0-9]", "", pending.lower())
                    common_caption = (
                        "commonstock" in pending_key
                        and ("parvalue" in pending_key or "sharesauthorized" in pending_key)
                    )
                    if common_caption:
                        pending_common_stock = True
                    elif not pending_common_stock:
                        section = pending
                pending = label
            continue
        label_key = re.sub(r"[^a-z0-9]", "", label.lower())
        share_caption = "sharesoutstanding" in label_key or "sharesissued" in label_key
        if pending_common_stock or (
            pending is not None
            and "commonstock" in re.sub(r"[^a-z0-9]", "", pending.lower())
            and share_caption
        ):
            label, section, pending = "common stock, $0.01 par value", "", None
            pending_common_stock = False
        elif not label and pending is not None:  # wrapped label: 'Shares used in ...' + values
            label, pending = pending, None
        elif pending is not None:
            section, pending = pending, None
        for j, raw in vals:
            if len(_parts(raw)) > 1:  # merged cell: structure error, do not guess
                stats["merged_cells"] += 1
                continue
            if periods:
                pj = min(periods, key=lambda h: (abs(h - j), -h))
                period = periods[pj]
            else:
                period = f"c{j}"
            sc = row_scale(section, label, raw, caption, cap_scale)
            recs.append({"section": norm_label(section), "label": norm_label(label),
                         "period": period, "raw": raw, "value": to_number(raw, sc), "scale": sc})
        if norm_label(label).startswith("total"):
            section = ""
    tidy = pd.DataFrame(recs, columns=["section", "label", "period", "raw", "value", "scale"])
    tidy = tidy.drop_duplicates(["section", "label", "period"], keep="first")
    return tidy, stats


def wide(tidy: pd.DataFrame) -> pd.DataFrame:
    if tidy.empty:
        return tidy
    periods = list(dict.fromkeys(tidy["period"]))
    rows = {}
    for r in tidy.itertuples():  # keep reading order of rows and periods
        rows.setdefault((r.section, r.label), {})[r.period] = r.value
    return pd.DataFrame([{"section": k[0], "label": k[1], **v} for k, v in rows.items()],
                        columns=["section", "label"] + periods)




# ------------------------------------------------------------------ extractors
PLUMBER_TEXT = {"vertical_strategy": "text", "horizontal_strategy": "text",
                "snap_tolerance": 3, "join_tolerance": 3, "intersection_tolerance": 5}


def ruling_count(page, bbox=None):
    r = page.within_bbox(bbox) if bbox else page
    hz = [l for l in r.lines if abs(l["top"] - l["bottom"]) < 1]
    thin = [x for x in r.rects if x["height"] < 2]
    return len(hz) + len(thin)


def quality(rep):
    if rep.get("accuracy") is None:  # pdfplumber: no text-assignment accuracy
        return 100 - 0.5 * rep["whitespace"] - 20
    return rep["accuracy"] - 0.5 * rep["whitespace"]


def ref_numbers(page, bbox=None):
    """Numbers printed on the page (or inside bbox), minus header years and the footer line."""
    region = page.within_bbox(bbox) if bbox else page
    lines = (region.extract_text() or "").splitlines()
    lines = lines if bbox else lines[:-1]
    return Counter(n for n in numbers("\n".join(lines)) if not YEAR_ONLY.match(n))


def coverage(df, ref):
    got = Counter(numbers(" ".join(map(str, df.fillna("").values.ravel()))))
    return sum((got & ref).values()) / max(sum(ref.values()), 1)


def to_area(bbox, page_h):
    """top-left [x0, top, x1, bottom] -> Camelot table_areas 'x1,y1,x2,y2' (bottom-left origin)."""
    x0, top, x1, bottom = bbox
    return f"{x0:.1f},{page_h - top:.1f},{x1:.1f},{page_h - bottom:.1f}"


def bbox_topleft(t, page_h):
    """Camelot _bbox is PDF-native bottom-left (x0, y0, x1, y1) -> [x0, top, x1, bottom]."""
    x0, y0, x1, y1 = t._bbox
    return [round(x0, 1), round(page_h - y1, 1), round(x1, 1), round(page_h - y0, 1)]


def page_caption(page, n_lines=8):
    return " ".join((page.extract_text() or "").splitlines()[:n_lines])


def run_flavor(pdf_path, page, flavor, cfg, bbox=None):
    """-> list of (df, report, bbox_topleft) for one method."""
    h = float(page.height)
    if flavor == "pdfplumber":
        region = page.within_bbox(bbox) if bbox else page
        out = []
        for t in region.find_tables(table_settings=PLUMBER_TEXT):
            df = pd.DataFrame(t.extract()).fillna("")
            ws = (df.astype(str).apply(lambda c: c.str.strip()) == "").values.mean() * 100
            out.append((df, {"accuracy": None, "whitespace": round(ws, 2)},
                        [round(v, 1) for v in t.bbox]))
        return out
    kw = dict(cfg.get(flavor) or {}) if flavor == "stream" else {}
    if bbox:
        kw["table_areas"] = [to_area(bbox, h)]
    ts = camelot.read_pdf(str(pdf_path), pages=str(page.page_number), flavor=flavor,
                          suppress_stdout=True, **kw)
    return [(t.df, t.parsing_report, bbox_topleft(t, h)) for t in ts]


def placement(ts, ref, caption):
    """Share of the printed numbers the cleaner could place in a (label, period) cell - catches
    structure losses the parsing report cannot see (e.g. network dropping the label column)."""
    placed = 0
    for df, _, _ in ts:
        tidy, st = clean_table(df, caption)
        placed += len(tidy[tidy["label"] != ""]) if st["periods"] else 0
    return min(placed / max(sum(ref.values()), 1), 1.0)


def extract_best(pdf_path, page, cfg, bbox=None):
    """Hybrid extractor. Rulings pick the first flavor; a candidate is accepted when
    quality > accept_score and coverage/placement >= min_coverage; otherwise the next flavor is
    tried and the best (coverage ok, placement, quality) wins. Returns dict(method, tables=
    [(df, rep, bbox)], quality, coverage, placement, accepted, tried)."""
    ref, caption = ref_numbers(page, bbox), page_caption(page)
    lat = ruling_count(page, bbox) >= cfg["min_rulings"]
    order = ["lattice", "stream"] if lat else ["stream", "lattice"]
    order += [f for f in cfg.get("fallback_flavors", []) if f not in order] + ["pdfplumber"]
    best, tried, mc = None, [], cfg["min_coverage"]
    for fl in order:
        try:
            ts = run_flavor(pdf_path, page, fl, cfg, bbox)
        except Exception as e:  # a failing flavor is logged, never fatal
            tried.append(f"{fl}:error({type(e).__name__})")
            continue
        if not ts:
            tried.append(f"{fl}:none")
            continue
        q = max(quality(r) for _, r, _ in ts)
        cov = coverage(pd.concat([d for d, _, _ in ts], axis=0, ignore_index=True), ref)
        pl = placement(ts, ref, caption)
        tried.append(f"{fl}:q={q:.1f},cov={cov:.2f},placed={pl:.2f}")
        ok = q > cfg["accept_score"] and cov >= mc and pl >= mc
        cand = {"method": fl, "tables": ts, "quality": q, "coverage": cov, "placement": pl,
                "accepted": ok}
        if best is None or (cov >= mc, pl, q) > (best["coverage"] >= mc, best["placement"],
                                                 best["quality"]):
            best = cand
        if ok:
            break
    if best is None:
        return {"method": None, "tables": [], "quality": None, "coverage": 0.0,
                "placement": 0.0, "accepted": False, "tried": tried}
    best["tried"] = tried
    return best


def managed_tables(pdf_path, page, mcfg):
    from managed import analyze_page
    from managed.textract import tables as tx_tables
    resp, src = analyze_page(pdf_path, page.page_number, mcfg)
    if resp is None:
        return None, src
    return [(df, {"accuracy": None, "whitespace": 0.0}, None) for df in tx_tables(resp)], src


def extract_best_df(pdf_path, page_no=1):
    """Cleaned tidy cells of the biggest table on one page (used by the regression tests)."""
    cfg = load_params("tables")
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_no - 1]
        res = extract_best(pdf_path, page, cfg)
        cap = page_caption(page)
    tidies = [clean_table(df, cap)[0] for df, _, _ in res["tables"]]
    return max(tidies, key=len) if tidies else pd.DataFrame(
        columns=["section", "label", "period", "raw", "value", "scale"])


# ------------------------------------------------------------------ stage
LOG_FIELDS = ["doc_id", "stem", "page", "table", "kind", "method", "accuracy", "whitespace",
              "quality", "coverage", "placement", "accepted", "tried", "managed", "rulings", "rows", "cols",
              "cells", "merged_cells", "periods", "scale", "bbox", "camelot_version", "seconds"]


def process_pdf(pdf_path, out, doc_id, cfg, mcfg, log, only_pages=None):
    stem, n_tables, written = pdf_path.stem, 0, set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pno = page.page_number
            if only_pages and pno not in only_pages:
                continue
            txt = page.extract_text() or ""
            if len(numbers(txt)) < cfg["min_numbers"]:
                continue
            t0 = time.perf_counter()
            res = extract_best(pdf_path, page, cfg)
            managed = ""
            if res["quality"] is None or res["quality"] < cfg["managed_below_score"]:
                mt, managed = managed_tables(pdf_path, page, mcfg)
                if mt:
                    res.update(method="textract", tables=mt, quality=None, accepted=True,
                               placement=placement(mt, ref_numbers(page), page_caption(page)))
            kind, caption = statement_kind(txt), page_caption(page)
            biggest = None
            for k, (df, rep, bbox) in enumerate(res["tables"], 1):
                base = f"{stem}_p{pno:04d}_t{k}"
                tidy, st = clean_table(df, caption)
                df.to_csv(out / f"{base}.raw.csv", index=False, header=False)
                tidy.to_csv(out / f"{base}.cells.csv", index=False)
                wide(tidy).to_csv(out / f"{base}.clean.csv", index=False)
                if biggest is None or len(tidy) > len(biggest):
                    biggest = tidy
                log.writerow({"doc_id": doc_id, "stem": stem, "page": pno, "table": k,
                              "kind": kind or "", "method": res["method"],
                              "accuracy": rep.get("accuracy"), "whitespace": rep.get("whitespace"),
                              "quality": round(quality(rep), 2),
                              "coverage": round(res["coverage"], 3),
                              "placement": round(res["placement"], 3), "accepted": res["accepted"],
                              "tried": " ".join(res["tried"]), "managed": managed,
                              "rulings": ruling_count(page), "rows": df.shape[0],
                              "cols": df.shape[1], "cells": len(tidy), **st,
                              "scale": scale_from_caption(caption), "bbox": bbox,
                              "camelot_version": camelot.__version__,
                              "seconds": round(time.perf_counter() - t0, 2)})
                n_tables += 1
            if kind and kind not in written and biggest is not None and not biggest.empty:
                biggest.to_csv(out / f"{stem}_{kind}.cells.csv", index=False)
                wide(biggest).to_csv(out / f"{stem}_{kind}.clean.csv", index=False)
                written.add(kind)  # first page of each statement wins
            print(f"  p{pno:>3} {kind or '':20s} {res['method'] or '-':10s} "
                  f"tables={len(res['tables'])} {' '.join(res['tried'])}")
    return n_tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, nargs="+", default=[RENDERED], help="PDFs or folders")
    ap.add_argument("--out", type=Path, default=TABLES)
    ap.add_argument("--pages", type=int, nargs="*", help="only these 1-based pages")
    a = ap.parse_args()
    cfg, mcfg = load_params("tables"), load_params("managed")
    manifest = load_manifest()
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "tables_log.csv", "w", newline="") as f:
        log = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        log.writeheader()
        for p in list_pdfs(a.input):
            print(p.name)
            doc_id = manifest.get(p.stem, {}).get("accession", p.stem)
            n = process_pdf(p, a.out, doc_id, cfg, mcfg, log, set(a.pages or []))
            print(f"{p.name}: {n} tables")


if __name__ == "__main__":
    main()
