"""Part 0 - download stage: fetch the pinned filings, unpack full-submission.txt, cache companyfacts.

Output: data/raw/sec-edgar-filings/<TICKER>/<FORM>/<accession>/
          full-submission.txt, primary-document.html, unpacked/ (iXBRL .htm, .xsd, linkbases)
        data/raw/xbrl/companyfacts_CIK<cik>.json  (cross-check only)
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, load_params

KEEP = {".htm", ".html", ".xml", ".xsd"}  # no images
CIK_RE = re.compile(r"CENTRAL INDEX KEY:\s*(\d+)")


def unpack(sub: Path) -> Path:
    """Split full-submission.txt into its original files so Arelle can resolve the filing."""
    out = sub.parent / "unpacked"
    out.mkdir(parents=True, exist_ok=True)
    raw = sub.read_text(errors="ignore")
    unpacked = 0
    for doc in re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", raw, re.S):
        name = re.search(r"<FILENAME>([^\n<]+)", doc)
        body = re.search(r"<TEXT>\n?(.*?)</TEXT>", doc, re.S)
        if not (name and body):
            continue
        fn = name.group(1).strip()
        if Path(fn).suffix.lower() not in KEEP:
            continue
        text = body.group(1)  # XML docs sit in <XBRL>/<XML>
        x = re.search(r"<(XBRL|XML)>\n?(.*?)</\1>", text, re.S)
        (out / fn).write_text(x.group(2) if x else text, encoding="utf-8")
        unpacked += 1
    print(f"unpacked {sub.parent.name}: {unpacked} files -> {out.resolve()}")
    return out


def companyfacts(cik: str, ua: str) -> Path:
    # Imported lazily so `unpack` (and this module) stay importable without the network stack,
    # which the CI smoke job deliberately does not install.
    import requests

    cik = cik.zfill(10)
    out = RAW / "xbrl" / f"companyfacts_CIK{cik}.json"
    if out.exists():  # filings never change once accepted: cache
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                     headers={"User-Agent": ua}, timeout=30)
    r.raise_for_status()
    out.write_text(json.dumps(r.json()), encoding="utf-8")
    return out


def main():
    from sec_edgar_downloader import Downloader

    p = load_params("download")
    ua = f"{p['user_agent_name']} {p['user_agent_email']}"
    dl = Downloader(p["user_agent_name"], p["user_agent_email"], str(RAW))
    for form in p["forms"]:
        n = dl.get(form, p["ticker"], limit=p["limit_per_form"], after=p["after"],
                   before=p["before"], download_details=True)
        print(f"{p['ticker']} {form}: {n} filing(s)")
        time.sleep(0.5)  # far below the 10 requests/second limit

    cik = None
    for sub in sorted(RAW.rglob("full-submission.txt")):
        out = unpack(sub)
        m = CIK_RE.search(sub.read_text(errors="ignore")[:5000])
        cik = cik or (m.group(1) if m else None)
        xsd = list(out.glob("*.xsd"))
        print(f"  schemas: {len(xsd)}")
    if cik:
        print("companyfacts ->", companyfacts(cik, ua).name)
    mb = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e6
    print(f"data/raw = {mb:.1f} MB ({'OK' if mb < 100 else 'OVER'} 100 MB budget)")


if __name__ == "__main__":
    main()
