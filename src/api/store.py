"""Read-only data access for the LANTERN serving API.

The API is a thin view over the artifacts the DVC pipeline already writes:
provenance JSONL + Markdown (Parts 5-6), the table log and clean grids
(Part 2), XBRL facts/comparison (Part 11) and the evaluation/benchmark
reports (Parts 9-10). Nothing here mutates the pipeline outputs.

Data resolution order:
  1. ``$LANTERN_DATA_ROOT`` when set (any directory laid out like ``data/``),
  2. ``data/serve`` when a deployment bundle exists (see
     ``src/api/build_bundle.py``) -- this is the copy that ships to Replit/Vercel,
  3. the repository ``data/`` directory (local, DVC-pulled).
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
STEM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class NotFound(Exception):
    """A requested stem, page, table or fact is not present in the corpus."""


def _resolve_root() -> Path:
    env = os.environ.get("LANTERN_DATA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    bundle = REPO_ROOT / "data" / "serve"
    if (bundle / "export").is_dir():
        return bundle
    return REPO_ROOT / "data"


DATA_ROOT = _resolve_root()
EXPORT_DIR = DATA_ROOT / "export"
TABLES_DIR = DATA_ROOT / "tables"
XBRL_DIR = DATA_ROOT / "xbrl"
BENCH_DIR = DATA_ROOT / "bench"
REPORTS_DIR = DATA_ROOT / "reports" if (DATA_ROOT / "reports").is_dir() else REPO_ROOT / "reports"


# --------------------------------------------------------------------------- #
# small caching helpers: files are parsed once per (path, mtime, size)
# --------------------------------------------------------------------------- #
def _key(path: Path) -> tuple[str, int, int]:
    try:
        st = path.stat()
        return (str(path), st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        return (str(path), -1, -1)


_cache: dict[str, tuple[tuple[str, int, int], Any]] = {}


def _cached(path: Path, loader) -> Any:
    key = _key(path)
    hit = _cache.get(str(path))
    if hit is not None and hit[0] == key:
        return hit[1]
    value = loader(path)
    _cache[str(path)] = (key, value)
    return value


def _read_jsonl_file(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _read_csv_file(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path: Path) -> Any:
    return _cached(path, lambda p: json.loads(p.read_text(encoding="utf-8")))


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return _cached(path, _read_csv_file)


def read_text(path: Path) -> str:
    if not path.exists():
        raise NotFound(f"no such file: {path.name}")
    return _cached(path, lambda p: p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# filings and provenance blocks
# --------------------------------------------------------------------------- #
def _check_stem(stem: str) -> str:
    if not STEM_RE.match(stem or "") or ".." in stem:
        raise NotFound(f"invalid filing id: {stem!r}")
    return stem


def _export_path(stem: str, suffix: str) -> Path:
    path = EXPORT_DIR / f"{_check_stem(stem)}{suffix}"
    if not path.exists():
        raise NotFound(f"no filing {stem!r} (expected {path.name})")
    return path


def list_stems() -> list[str]:
    if not EXPORT_DIR.is_dir():
        return []
    return sorted(p.stem for p in EXPORT_DIR.glob("*.jsonl"))


def blocks(stem: str) -> list[dict]:
    return _cached(_export_path(stem, ".jsonl"), _read_jsonl_file)


def _header(stem: str) -> dict:
    rows = blocks(stem)
    if not rows:
        raise NotFound(f"filing {stem!r} has no blocks")
    first = rows[0]
    return {
        "stem": stem,
        "doc_id": first.get("doc_id"),
        "company": first.get("company"),
        "cik": first.get("cik"),
        "ticker": first.get("ticker"),
        "form": first.get("form"),
        "fiscal_year": first.get("fiscal_year"),
        "fiscal_period": first.get("fiscal_period"),
        "source_path": first.get("source_path"),
        "sha256": first.get("sha256"),
    }


def filing_summary(stem: str) -> dict:
    rows = blocks(stem)
    pages = [r["page"] for r in rows if isinstance(r.get("page"), int)]
    ocr = sum(1 for r in rows if r.get("ocr"))
    sections = {r.get("section") for r in rows if r.get("section")}
    return {
        **_header(stem),
        "pages": max(pages) if pages else 0,
        "blocks": len(rows),
        "sections": len(sections),
        "tables": sum(1 for r in rows if r.get("block_type") == "Table"),
        "ocr_blocks": ocr,
        "ocr_share": round(ocr / len(rows), 4) if rows else 0.0,
        "markdown_chars": len(read_text(_export_path(stem, ".md"))),
    }


def list_filings() -> list[dict]:
    return [filing_summary(stem) for stem in list_stems()]


def filing_detail(stem: str) -> dict:
    summary = filing_summary(stem)
    rows = blocks(stem)
    summary["section_list"] = sections(stem)
    summary["pages_list"] = sorted({r["page"] for r in rows if isinstance(r.get("page"), int)})
    summary["table_count"] = len(table_log(stem=stem))
    summary["xbrl_facts"] = sum(1 for f in xbrl_facts(stem=stem, limit=None)["items"])
    return summary


def sections(stem: str) -> list[dict]:
    """Ordered section spans (the Part 6 ``section`` field, grouped)."""
    out: list[dict] = []
    for row in blocks(stem):
        name = row.get("section") or "(unsectioned)"
        if not out or out[-1]["section"] != name:
            out.append({"section": name, "first_page": row.get("page"),
                        "last_page": row.get("page"), "blocks": 1})
        else:
            out[-1]["last_page"] = row.get("page")
            out[-1]["blocks"] += 1
    return out


def page(stem: str, page_number: int) -> dict:
    rows = [r for r in blocks(stem) if r.get("page") == page_number]
    if not rows:
        raise NotFound(f"{stem} has no page {page_number}")
    return {
        "stem": stem,
        "page": page_number,
        "blocks": rows,
        "text": "\n".join(r["text"] for r in rows if r.get("text")),
    }


def markdown(stem: str) -> str:
    return read_text(_export_path(stem, ".md"))


def query_blocks(stem: str, *, page_number: int | None = None, block_type: str | None = None,
                 section: str | None = None, q: str | None = None, ocr: bool | None = None,
                 offset: int = 0, limit: int = 100) -> dict:
    rows = blocks(stem)
    if page_number is not None:
        rows = [r for r in rows if r.get("page") == page_number]
    if block_type:
        rows = [r for r in rows if (r.get("block_type") or "").lower() == block_type.lower()]
    if section:
        needle = section.lower()
        rows = [r for r in rows if needle in (r.get("section") or "").lower()]
    if ocr is not None:
        rows = [r for r in rows if bool(r.get("ocr")) is ocr]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in (r.get("text") or "").lower()]
    total = len(rows)
    window = rows[offset:offset + limit]
    return {"stem": stem, "total": total, "offset": offset, "limit": limit, "items": window}


def search(q: str, stem: str | None = None, limit: int = 50, context: int = 120) -> dict:
    if not q or not q.strip():
        raise ValueError("q must be a non-empty query string")
    needle = q.lower()
    stems = [stem] if stem else list_stems()
    hits: list[dict] = []
    for s in stems:
        for row in blocks(s):
            text = row.get("text") or ""
            pos = text.lower().find(needle)
            if pos < 0:
                continue
            start = max(0, pos - context)
            end = min(len(text), pos + len(q) + context)
            hits.append({
                "stem": s,
                "page": row.get("page"),
                "block_id": row.get("block_id"),
                "block_type": row.get("block_type"),
                "section": row.get("section"),
                "snippet": ("..." if start else "") + text[start:end] + ("..." if end < len(text) else ""),
            })
            if len(hits) >= limit:
                return {"query": q, "total": len(hits), "truncated": True, "items": hits}
    return {"query": q, "total": len(hits), "truncated": False, "items": hits}


# --------------------------------------------------------------------------- #
# tables (Part 2)
# --------------------------------------------------------------------------- #
_TABLE_NUMERIC = {"accuracy", "whitespace", "quality", "coverage", "placement", "scale",
                  "seconds", "rulings", "rows", "cols", "cells", "merged_cells", "periods"}


def _coerce_row(row: dict) -> dict:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key in _TABLE_NUMERIC:
            if value in (None, ""):
                out[key] = None
                continue
            try:
                out[key] = float(value)
                continue
            except ValueError:
                pass
        elif key == "accepted" and value in ("True", "False"):
            out[key] = value == "True"
            continue
        out[key] = value
    return out


def table_log(stem: str | None = None, *, accepted: bool | None = None,
              method: str | None = None, page_number: int | None = None,
              limit: int = 500) -> list[dict]:
    rows = [_coerce_row(r) for r in read_csv(TABLES_DIR / "tables_log.csv")]
    if stem:
        rows = [r for r in rows if r.get("stem") == stem]
    if accepted is not None:
        rows = [r for r in rows if bool(r.get("accepted")) is accepted]
    if method:
        rows = [r for r in rows if (r.get("method") or "").lower() == method.lower()]
    if page_number is not None:
        rows = [r for r in rows if str(r.get("page")) == str(page_number)]
    return rows[:limit]


def table_names(stem: str) -> list[str]:
    """Clean-grid names for a filing: statement names and ``p<page>_t<n>`` ids."""
    prefix = f"{_check_stem(stem)}_"
    names: list[str] = []
    if TABLES_DIR.is_dir():
        for path in sorted(TABLES_DIR.glob(f"{prefix}*.clean.csv")):
            names.append(path.name[len(prefix):-len(".clean.csv")])
    return names


def table_grid(stem: str, name: str) -> dict:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", name or "")
    if not safe or safe != name:
        raise NotFound(f"invalid table name: {name!r}")
    path = TABLES_DIR / f"{_check_stem(stem)}_{safe}.clean.csv"
    rows = read_csv(path)
    if not rows:
        raise NotFound(f"no clean grid {path.name}")
    columns = list(rows[0].keys())
    return {"stem": stem, "table": name, "columns": columns,
            "rows": [[r.get(c) for c in columns] for r in rows]}


# --------------------------------------------------------------------------- #
# XBRL (Part 11)
# --------------------------------------------------------------------------- #
def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def xbrl_facts(stem: str | None = None, *, concept: str | None = None, label: str | None = None,
               prefix: str | None = None, q: str | None = None, limit: int | None = 200,
               offset: int = 0) -> dict:
    rows = read_csv(XBRL_DIR / "facts.csv")
    if stem:
        rows = [r for r in rows if r.get("stem") == stem]
    if concept:
        rows = [r for r in rows if r.get("concept") == concept]
    if prefix:
        rows = [r for r in rows if r.get("prefix") == prefix]
    if label:
        needle = label.lower()
        rows = [r for r in rows if needle in (r.get("label") or "").lower()]
    if q:
        needle = q.lower()
        rows = [r for r in rows
                if needle in (r.get("concept") or "").lower()
                or needle in (r.get("label") or "").lower()]
    total = len(rows)
    for row in rows:
        row["value_num"] = _number(row.get("value"))
    window = rows[offset:] if limit is None else rows[offset:offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "items": window}


def xbrl_comparison(stem: str | None = None, *, statement: str | None = None,
                    status: str | None = None, path: str | None = None,
                    limit: int = 500) -> list[dict]:
    rows = read_csv(XBRL_DIR / "comparison.csv")
    if stem:
        rows = [r for r in rows if r.get("stem") == stem]
    if statement:
        rows = [r for r in rows if r.get("statement") == statement]
    if status:
        rows = [r for r in rows if (r.get("status") or "").lower() == status.lower()]
    if path:
        rows = [r for r in rows if r.get("path") == path]
    for row in rows:
        row["pdf_value_num"] = _number(row.get("pdf_value"))
        row["xbrl_value_num"] = _number(row.get("xbrl_value"))
    return rows[:limit]


def xbrl_summary() -> list[dict]:
    """Match rate per (stem, path, statement), mirroring reports/xbrl.md."""
    groups: dict[tuple, dict] = {}
    for row in read_csv(XBRL_DIR / "comparison.csv"):
        key = (row.get("stem"), row.get("path"), row.get("statement"))
        bucket = groups.setdefault(key, {"stem": key[0], "path": key[1], "statement": key[2],
                                         "matched": 0, "total": 0, "mismatch": 0})
        bucket["total"] += 1
        if (row.get("status") or "").lower() == "match":
            bucket["matched"] += 1
        else:
            bucket["mismatch"] += 1
    out = []
    for bucket in groups.values():
        bucket["match_rate"] = round(bucket["matched"] / bucket["total"], 4) if bucket["total"] else None
        out.append(bucket)
    return sorted(out, key=lambda r: (r["stem"] or "", r["path"] or "", r["statement"] or ""))


# --------------------------------------------------------------------------- #
# metrics and benchmarks (Parts 9-10)
# --------------------------------------------------------------------------- #
def metrics() -> dict:
    data = read_json(REPORTS_DIR / "metrics.json") if (REPORTS_DIR / "metrics.json").exists() else {}
    formats = read_csv(EXPORT_DIR / "format_sizes.csv")
    return {"metrics": data, "format_sizes": formats, "xbrl_summary": xbrl_summary(),
            "reports": _report_index()}


def _report_index() -> list[dict]:
    if not REPORTS_DIR.is_dir():
        return []
    return [{"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(REPORTS_DIR.glob("*.md"))]


def benchmarks() -> list[dict]:
    out: list[dict] = []
    if BENCH_DIR.is_dir():
        for path in sorted(BENCH_DIR.glob("*.csv")):
            rows = read_csv(path)
            for row in rows:
                row["seconds"] = _number(row.get("seconds"))
                row["peak_rss_mb"] = _number(row.get("peak_rss_mb"))
            out.extend(rows)
    return out


def corpus_stats() -> dict:
    stems = list_stems()
    return {
        "filings": len(stems),
        "stems": stems,
        "blocks": sum(filing_summary(s)["blocks"] for s in stems),
        "tables": len(table_log(limit=10 ** 9)),
        "xbrl_facts": len(read_csv(XBRL_DIR / "facts.csv")),
        "data_root": str(DATA_ROOT),
    }
