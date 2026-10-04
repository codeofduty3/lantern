"""Shared helpers for every LANTERN stage: paths, params, manifest, page finders, reports."""
import csv
import hashlib
import io
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
RENDERED = DATA / "rendered"
PARSED = DATA / "parsed"
TABLES = DATA / "tables"
LAYOUT = DATA / "layout"
FIGURES = DATA / "figures"
DOCLING = DATA / "docling"
EXPORT = DATA / "export"
XBRL = DATA / "xbrl"
BENCH = DATA / "bench"
MANAGED = DATA / "managed"
GROUND_TRUTH = DATA / "ground_truth"
REPORTS = ROOT / "reports"
FIXTURES = ROOT / "tests" / "fixtures"
FIXTURE_GT = FIXTURES / "gt"
CONFIG = ROOT / "config"

# Numeric token as used in Lab 9: (1,234)  -5  $9,871  4.12
NUM_RE = re.compile(r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?")
STATEMENT_KINDS = {  # matched against a page's first lines (10-Q titles add CONDENSED)
    "income_statement": r"CONSOLIDATED\s*STATEMENTS?\s*OF\s*(OPERATIONS|INCOME|EARNINGS)",
    "comprehensive_income": r"CONSOLIDATED\s*STATEMENTS?\s*OF\s*COMPREHENSIVE",
    "balance_sheet": r"CONSOLIDATED\s*BALANCE\s*SHEETS?",
    "equity": r"CONSOLIDATED\s*STATEMENTS?\s*OF\s*(SHAREHOLDERS|STOCKHOLDERS)",
    "cash_flows": r"CONSOLIDATED\s*STATEMENTS?\s*OF\s*CASH\s*FLOWS",
}
NOT_A_STATEMENT = re.compile(r"\bINDEX\b", re.I)
ITEM_LINE = re.compile(r"^\s*ITEM\s*\d", re.I)
# What may follow a title on its line: upper-case words ("... AND COMPREHENSIVE INCOME"),
# "continued", "(unaudited)". Prose that merely names a statement fails this.
TITLE_TAIL = re.compile(r"(?:[\s,]|[A-Z’'&()-]+|\(?continued\)?|\(unaudited\))*")
MANIFEST_FIELDS = ["stem", "accession", "cik", "ticker", "company", "form", "period",
                   "source_file", "renderer", "renderer_version", "page_format", "sha256"]


def load_params(section=None):
    p = yaml.safe_load((ROOT / "params.yaml").read_text())
    return p[section] if section else p


def sha256(path=None, data: bytes = None):
    h = hashlib.sha256()
    if data is not None:
        h.update(data)
        return h.hexdigest()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path) -> str:
    """Repo-relative path string for provenance fields (no machine-specific prefixes)."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def ensure_file(url: str, dest, digest: str = None, label: str = "") -> Path:
    """Download `url` to `dest` once, atomically, verifying `digest` when given.

    Refuses HTML responses: hosts like Dropbox answer a removed file with a 200 HTML
    page, which torch would later fail to unpickle with a confusing error.
    """
    dest = Path(dest)
    if dest.exists() and (not digest or sha256(dest) == digest):
        return dest
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    name = label or dest.name
    print(f"{name}: downloading {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "html" in ctype.lower():
            raise RuntimeError(f"{name}: {url} returned {ctype}, not a file "
                               "(the host may have removed it)")
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    got = sha256(part)
    if digest and got != digest:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"{name}: sha256 {got} does not match the pinned {digest}")
    part.replace(dest)
    print(f"{name}: saved {rel(dest)} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def setup_tesseract():
    """Honour TESSERACT_CMD (needed on Windows if tesseract is not on PATH)."""
    import pytesseract
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract


def load_manifest() -> dict:
    """stem -> manifest row (data/rendered/manifest.csv, written by render.py)."""
    m = RENDERED / "manifest.csv"
    if not m.exists():
        return {}
    with open(m, newline="") as f:
        return {r["stem"]: r for r in csv.DictReader(f)}


def list_pdfs(inputs) -> list:
    """Expand files/folders into a sorted list of PDFs."""
    out = []
    for p in inputs:
        p = Path(p)
        out += [p] if p.is_file() else sorted(p.glob("*.pdf"))
    return out


def page_pdf_bytes(pdf_path, pno: int) -> bytes:
    """One page (1-based) as a standalone PDF - for page hashes, managed APIs, fixtures."""
    import pypdfium2 as pdfium
    src = pdfium.PdfDocument(str(pdf_path))
    dst = pdfium.PdfDocument.new()
    dst.import_pages(src, [pno - 1])
    buf = io.BytesIO()
    dst.save(buf)
    return buf.getvalue()


def numbers(text):
    """Numeric tokens normalised: drop $ and trailing punctuation, keep sign/parens."""
    out = []
    for m in NUM_RE.finditer(text or ""):
        t = m.group().replace("$", "").rstrip(",")
        if t.count("(") != t.count(")"):
            t = t.strip("()")
        if any(ch.isdigit() for ch in t):
            out.append(t)
    return out


def statement_kind(text, n_lines=6):
    """Which primary statement a page is (title line in its first lines), else None.

    The title must be a line of its own: prose such as "...included in the consolidated
    statements of income for the..." can wrap into the first lines of a notes page. One
    "Item 1. Financial Statements" line may precede the title (first 10-Q statement page);
    two or more Item lines mean a table of contents."""
    lines = (text or "").splitlines()[:n_lines]
    if NOT_A_STATEMENT.search("\n".join(lines)) or sum(bool(ITEM_LINE.match(l)) for l in lines) > 1:
        return None
    for kind, pat in STATEMENT_KINDS.items():
        for l in lines:
            m = re.match(rf"\s*(?:CONDENSED\s*)?{pat}", l, re.I)
            if m and TITLE_TAIL.fullmatch(l[m.end():]):
                return kind
    return None


def find_statement_page(pdf, kind=None):
    """1-based page of a primary statement (IS/BS, or a given kind); most numbers wins."""
    best, best_n, fallback, fallback_n = None, -1, 1, -1
    for page in pdf.pages:
        txt = page.extract_text() or ""
        n = len(numbers(txt))
        if n > fallback_n:
            fallback, fallback_n = page.page_number, n
        k = statement_kind(txt)
        ok = k in ("income_statement", "balance_sheet") if kind is None else k == kind
        if ok and n > best_n:
            best, best_n = page.page_number, n
    return best or fallback


def find_prose_page(pdf, min_words=300):
    """1-based page with lots of words and the lowest share of numbers."""
    best, best_ratio = 1, 1.0
    for page in pdf.pages:
        words = (page.extract_text() or "").split()
        if len(words) < min_words:
            continue
        ratio = len(numbers(" ".join(words))) / len(words)
        if ratio < best_ratio:
            best, best_ratio = page.page_number, ratio
    return best


AUTO_START, AUTO_END = "<!-- AUTO:START (generated, do not edit) -->", "<!-- AUTO:END -->"


def write_report(path: Path, title: str, auto_md: str, discussion_hint: str = ""):
    """Replace only the generated block of a report; keep everything the team wrote."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = f"{AUTO_START}\n{auto_md.rstrip()}\n{AUTO_END}"
    if path.exists() and AUTO_START in path.read_text(encoding="utf-8"):
        old = path.read_text(encoding="utf-8")
        new = re.sub(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END),
                     lambda _: block, old, flags=re.S)
    else:
        new = f"# {title}\n\n{block}\n\n## Discussion\n\n{discussion_hint}\n"
    path.write_text(new, encoding="utf-8")
