"""Part 0 - build the three committed test fixtures (run once; outputs go to Git, not DVC).

  tests/fixtures/scanned.pdf    3 pages of the 10-K rasterized and rebuilt image-only (OCR path)
  tests/fixtures/statement.pdf  the 10-K income statement page (born-digital)
  tests/fixtures/multicol.pdf   a multi-column page: params fixtures.multicol_pdf/page if given
                                (a page from another public SEC filing), else a synthetic two-column
                                render of a 10-K prose page (documented in tests/fixtures/README.md)
"""
import io
import json
import random
import sys
from pathlib import Path

import pdfplumber
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (FIXTURES, RENDERED, find_prose_page, find_statement_page, load_params,
                    page_pdf_bytes)


def scanify(img: Image.Image, rng: random.Random) -> Image.Image:
    """Mild scan artefacts: grayscale, skew, blur, JPEG compression."""
    g = img.convert("L").rotate(rng.uniform(-0.6, 0.6), fillcolor=255, resample=Image.BICUBIC)
    g = g.filter(ImageFilter.GaussianBlur(0.6))
    buf = io.BytesIO()
    g.save(buf, "JPEG", quality=55)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def synthetic_multicol(prose_text: str, out: Path):
    from playwright.sync_api import sync_playwright
    paras = "".join(f"<p>{p}</p>" for p in prose_text.split("\n\n") if p.strip()) or \
        f"<p>{prose_text}</p>"
    html = ("<html><body style='font:10pt Helvetica;margin:0.6in'>"
            "<h2 style='text-align:center'>Management's Discussion (two-column test layout)</h2>"
            f"<div style='column-count:2;column-gap:0.35in;text-align:justify'>{paras}</div>"
            "</body></html>")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html)
        pg.pdf(path=str(out), format="Letter", page_ranges="1")
        b.close()


def main():
    cfg = load_params("fixtures")
    tenk = (sorted(RENDERED.glob("*10K*.pdf")) or sorted(RENDERED.glob("*.pdf")))[0]
    FIXTURES.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7245)  # deterministic fixture
    with pdfplumber.open(tenk) as pdf:
        stmt = cfg["statement_page"] or find_statement_page(pdf, kind="income_statement")
        prose = find_prose_page(pdf)
        scan_pages = cfg["scanned_pages"] or [1, prose, stmt]
        imgs = [scanify(pdf.pages[n - 1].to_image(resolution=cfg["dpi"]).original, rng)
                for n in scan_pages]
        prose_text = pdf.pages[prose - 1].extract_text(layout=False) or ""
    imgs[0].save(FIXTURES / "scanned.pdf", "PDF", save_all=True, append_images=imgs[1:],
                 resolution=cfg["dpi"])
    (FIXTURES / "statement.pdf").write_bytes(page_pdf_bytes(tenk, stmt))

    if cfg["multicol_pdf"]:
        src_mc = Path(cfg["multicol_pdf"])
        (FIXTURES / "multicol.pdf").write_bytes(page_pdf_bytes(src_mc, cfg["multicol_page"]))
        mc_src = f"page {cfg['multicol_page']} of `{src_mc.name}` (public SEC filing)"
    else:
        synthetic_multicol(prose_text, FIXTURES / "multicol.pdf")
        mc_src = (f"SYNTHETIC: text of {tenk.name} page {prose} re-rendered in two CSS columns "
                  "(our filings have no multi-column page). Replace via params fixtures.multicol_pdf.")

    meta = {"scanned": {"source": tenk.name, "pages": scan_pages, "dpi": cfg["dpi"]},
            "statement": {"source": tenk.name, "page": stmt}, "multicol": mc_src}
    (FIXTURES / "fixtures.json").write_text(json.dumps(meta, indent=2))
    (FIXTURES / "README.md").write_text(
        "# Test fixtures (committed to Git; CI inputs)\n\n"
        f"- `scanned.pdf`: pages {scan_pages} of `{tenk.name}` rasterized at {cfg['dpi']} DPI "
        "with grayscale, skew, blur and JPEG artefacts, rebuilt as an image-only PDF "
        "(`src/make_fixtures.py`).\n"
        f"- `statement.pdf`: page {stmt} of `{tenk.name}` (income statement).\n"
        f"- `multicol.pdf`: {mc_src}\n"
        "- `gt/`: hand transcriptions (`<fixture>_p<N>.gt.txt`) and the statement table "
        "(`statement_p1_t1.gt.csv`); conventions in `gt/CONVENTIONS.md`.\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
