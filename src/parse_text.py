"""Part 1 - parse_pdfplumber stage: per-page text, word boxes, OCR fallback, OCR log.

Trigger (params ocr): empty (chars < min_chars) | garbled (junk_ratio > tau) | image (raster
coverage > image_area). Triggered pages are OCR'd with Tesseract at ocr.dpi; if the mean OCR
confidence is below ocr.managed_below_conf, the managed fallback (Part 7) is consulted.

Output (--out, default data/parsed):
  {stem}_p{NNNN}.txt     per-page text
  {stem}.words.jsonl     word boxes in PDF points, top-left origin
  ocr_log.csv            one row per page: engine, trigger reason, signals, mean confidence
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import pdfplumber
from pytesseract import Output

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NUM_RE, PARSED, RENDERED, list_pdfs, load_manifest, load_params, setup_tesseract

pytesseract = setup_tesseract()

CID_RE = re.compile(r"\(cid:\d+\)")
WORD_RE = re.compile(r"^[(\[\"'“‘]?[A-Za-z][A-Za-z'’.\-&/]*[)\]\"'”’,;:.?!]*$")
NUMISH_RE = re.compile(r"^[(\[]?[$€£]?" + NUM_RE.pattern + r"[%)\],;:.]*$")
SYMBOLS = set("$%—–-&•|()*/®™§†‡.,:;=+#<>▶►●○▪■□✓☐☒")
LOG_FIELDS = ["doc_id", "stem", "page", "engine", "reason", "chars", "tokens", "junk_ratio",
              "image_ratio", "ocr_mean_conf", "managed", "seconds"]


# ---------------------------------------------------------------- trigger signals
def is_junk(tok: str) -> bool:
    """Junk = missing-font-map glyphs, replacement chars, or mostly non-alphanumeric strings
    that are neither words, numbers nor common filing symbols (checkboxes, /s/, (“R&D”))."""
    if tok == "(cid)" or "\ufffd" in tok:
        return True
    core = tok.strip("()[]\"'“”‘’,;:.*")
    if not core or tok in SYMBOLS or core in SYMBOLS or core == "/s/":
        return False
    if WORD_RE.match(core) or NUMISH_RE.match(core):
        return False
    return sum(c.isalnum() for c in core) / len(core) < 0.5


def page_signals(page, text=None) -> dict:
    if text is None:
        text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
    chars = sum(1 for c in page.chars if c["text"].strip())
    tokens = CID_RE.sub(" (cid) ", text).split()
    junk = sum(map(is_junk, tokens))
    area = float(page.width * page.height)
    cov = 0.0
    for im in page.images:
        w = max(0.0, min(im["x1"], page.width) - max(im["x0"], 0))
        h = max(0.0, min(im["bottom"], page.height) - max(im["top"], 0))
        cov += w * h
    return {"chars": chars, "tokens": len(tokens),
            "junk_ratio": round(junk / len(tokens), 4) if tokens else 0.0,
            "image_ratio": round(min(cov / area, 1.0), 4) if area else 0.0}


def needs_ocr(sig: dict, cfg: dict):
    if sig["chars"] < cfg["min_chars"]:
        return True, "empty"
    if sig["junk_ratio"] > cfg["junk_ratio"]:
        return True, "garbled"
    if sig["image_ratio"] > cfg["image_area"]:
        return True, "image"
    return False, "text-layer"


# ---------------------------------------------------------------- OCR
def ocr_image(img, dpi: int, config: str, offset=(0.0, 0.0)):
    """Tesseract on a PIL image -> (text, words with bbox in points, mean conf)."""
    d = pytesseract.image_to_data(img, config=config, output_type=Output.DICT)
    k = 72 / dpi  # pixels -> points
    ox, oy = offset
    words, lines, prev = [], [], None
    for i, t in enumerate(d["text"]):
        c = float(d["conf"][i])
        if not t.strip() or c < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        if key != prev:
            lines.append([])
            prev = key
        lines[-1].append(t)
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        words.append({"text": t, "conf": c,
                      "bbox": [ox + x * k, oy + y * k, ox + (x + w) * k, oy + (y + h) * k]})
    mean = sum(w["conf"] for w in words) / max(len(words), 1)
    return "\n".join(" ".join(l) for l in lines), words, mean


def ocr_page(page, dpi: int, config: str):
    return ocr_image(page.to_image(resolution=dpi).original, dpi, config)


def managed_text(pdf_path, page, mcfg):
    """Cached/managed Textract text + words for a page, or None."""
    from managed import analyze_page
    from managed.textract import lines, mean_conf, text
    resp, src = analyze_page(pdf_path, page.page_number, mcfg)
    if resp is None:
        return None, src
    words = [{"text": l["text"], "conf": l["conf"], "bbox": l["bbox"]}
             for l in lines(resp, float(page.width), float(page.height))]
    return (text(resp), words, mean_conf(resp)), src


# ---------------------------------------------------------------- main loop
def parse_pdf(pdf_path, out_dir, stem, doc_id, cfg, mcfg, log):
    out = Path(out_dir)
    counts = {"text-layer": 0, "ocr": 0}
    with open(out / f"{stem}.words.jsonl", "w", encoding="utf-8") as wf, \
            pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t0 = time.perf_counter()
            n = page.page_number
            txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            sig = page_signals(page, txt)
            ocr, reason = needs_ocr(sig, cfg)
            engine, conf, managed = "pdfplumber", None, ""
            if ocr:
                txt, words, conf = ocr_page(page, cfg["dpi"], cfg["config"])
                engine = "tesseract"
                if conf < cfg["managed_below_conf"]:
                    res, managed = managed_text(pdf_path, page, mcfg)
                    if res:
                        txt, words, conf = res
                        engine = "textract"
                recs = [{"doc_id": doc_id, "page": n, "text": w["text"], "bbox": w["bbox"],
                         "units": "pt", "origin": "top-left", "extractor": engine,
                         "ocr": True, "conf": w["conf"]} for w in words]
            else:
                recs = [{"doc_id": doc_id, "page": n, "text": w["text"],
                         "bbox": [w["x0"], w["top"], w["x1"], w["bottom"]],
                         "units": "pt", "origin": "top-left", "extractor": "pdfplumber",
                         "ocr": False, "conf": None}
                        for w in page.extract_words(x_tolerance=1.5, use_text_flow=True)]
            (out / f"{stem}_p{n:04d}.txt").write_text(txt, encoding="utf-8")
            for r in recs:
                wf.write(json.dumps(r) + "\n")
            counts["ocr" if ocr else "text-layer"] += 1
            log.writerow({"doc_id": doc_id, "stem": stem, "page": n, "engine": engine,
                          "reason": reason, **sig,
                          "ocr_mean_conf": round(conf, 1) if conf is not None else "",
                          "managed": managed, "seconds": round(time.perf_counter() - t0, 3)})
    return counts


def extract_page_text(pdf_path, page_no=1):
    """Single-page entry point used by the regression tests."""
    cfg = load_params("ocr")
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_no - 1]
        txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
        if needs_ocr(page_signals(page, txt), cfg)[0]:
            txt = ocr_page(page, cfg["dpi"], cfg["config"])[0]
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, nargs="+", default=[RENDERED], help="PDFs or folders")
    ap.add_argument("--out", type=Path, default=PARSED)
    a = ap.parse_args()
    cfg, mcfg = load_params("ocr"), load_params("managed")
    manifest = load_manifest()
    pdfs = list_pdfs(a.input)
    if not pdfs:
        raise SystemExit(f"No PDFs found in {a.input}")
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "ocr_log.csv", "w", newline="") as f:
        log = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        log.writeheader()
        for p in pdfs:
            doc_id = manifest.get(p.stem, {}).get("accession", p.stem)
            c = parse_pdf(p, a.out, p.stem, doc_id, cfg, mcfg, log)
            print(f"{p.name}: {c['text-layer']} text-layer pages, {c['ocr']} OCR pages")


if __name__ == "__main__":
    main()
