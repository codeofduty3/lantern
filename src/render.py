"""Part 0 - render stage: filing HTML -> PDF with headless Chromium, plus manifest.csv.

Output: data/rendered/{TICKER}_{FORM}_{PERIOD}.pdf
        data/rendered/manifest.csv  (stem, accession, cik, ticker, company, form, period,
                                     source_file, renderer, renderer_version, page_format, sha256)
"""
import csv
import re
import sys
from importlib.metadata import version
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MANIFEST_FIELDS, RAW, RENDERED, load_params, rel, sha256

PER = re.compile(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})")
CIK = re.compile(r"CENTRAL INDEX KEY:\s*(\d+)")
NAME = re.compile(r"COMPANY CONFORMED NAME:\s*(.+)")


def details_file(d: Path) -> Path:  # v5 name first, then v4 name
    for n in ("primary-document.html", "filing-details.html"):
        if (d / n).exists():
            return d / n
    raise FileNotFoundError(d)


def meta(d: Path) -> dict:  # d = .../<TICKER>/<FORM>/<accession>
    hdr = (d / "full-submission.txt").read_text(errors="ignore")[:6000]
    per = PER.search(hdr).group(1)
    ticker, form = d.parts[-3], d.parts[-2]
    stem = f"{ticker}_{form.replace('-', '')}_{per}"
    return {"stem": stem, "accession": d.name, "cik": CIK.search(hdr).group(1).zfill(10),
            "ticker": ticker, "company": NAME.search(hdr).group(1).strip(), "form": form,
            "period": per, "source_file": rel(details_file(d))}


def main():
    cfg = load_params("render")
    RENDERED.mkdir(parents=True, exist_ok=True)
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for sub in sorted(RAW.rglob("full-submission.txt")):
            m = meta(sub.parent)
            out = RENDERED / f"{m['stem']}.pdf"
            page = browser.new_page()
            page.goto(details_file(sub.parent).resolve().as_uri(), wait_until="load",
                      timeout=cfg["timeout_ms"])
            page.pdf(path=str(out), format=cfg["page_format"], print_background=True)
            page.close()
            m.update({"renderer": "playwright-chromium",
                      "renderer_version": f"playwright {version('playwright')}; "
                                          f"chromium {browser.version}",
                      "page_format": cfg["page_format"], "sha256": sha256(out)})
            rows.append(m)
            print(f"rendered {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
        browser.close()
    with open(RENDERED / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
