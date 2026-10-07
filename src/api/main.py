"""LANTERN API -- a read-only FastAPI backend over the parsed corpus.

Run it locally:

    uvicorn src.api.main:app --reload

Swagger UI (with working "Try it out") is then at http://127.0.0.1:8000/docs and
the raw OpenAPI document at /openapi.json. The same app runs unchanged on
Replit (see .replit) and, via api/index.py, on Vercel.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import store
from .models import (
    BlockPage,
    ComparisonRow,
    Error,
    FactsResponse,
    FilingDetail,
    FilingSummary,
    Health,
    MarkdownResponse,
    MetricsResponse,
    PageResponse,
    SearchResponse,
    Section,
    TableGrid,
    TableRow,
    XbrlSummaryRow,
)

VERSION = "1.0.0"

DESCRIPTION = """
Read-only JSON API over the **Project LANTERN** corpus: Akamai 10-K/10-Q filings
parsed into layout-aware, XBRL-validated blocks with page/bbox provenance.

Every endpoint reads the artifacts the DVC pipeline writes. Use the section
groups below to browse filings, provenance blocks, tables, XBRL facts and the
evaluation/benchmark metrics.

> Tip: open any endpoint, press **Try it out**, edit the parameters and hit
> **Execute** to run it against the live corpus.
"""

TAGS = [
    {"name": "service", "description": "Liveness and corpus inventory."},
    {"name": "filings", "description": "Filings and their provenance blocks / Markdown."},
    {"name": "tables", "description": "Extracted tables: the extraction log and clean grids."},
    {"name": "xbrl", "description": "XBRL facts and the PDF-vs-XBRL comparison."},
    {"name": "analytics", "description": "Evaluation metrics, benchmarks and full-text search."},
]

app = FastAPI(
    title="LANTERN API",
    version=VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS,
    contact={"name": "codeofduty3", "url": "https://github.com/codeofduty3/lantern"},
    license_info={"name": "Coursework - DAMG 7245 Fall 2026"},
    servers=[{"url": "/", "description": "Current host (local, Replit or Vercel)"}],
)

# The Streamlit UI (or any browser client) is served from a different origin.
# Comma-separated allow-list via $LANTERN_CORS_ORIGINS, default "*" for the lab.
_origins = os.environ.get("LANTERN_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",")],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["service"], summary="Service banner", include_in_schema=False)
def root() -> dict:
    return {
        "service": "lantern-api",
        "version": VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "corpus": store.corpus_stats(),
    }


@app.get("/health", tags=["service"], response_model=Health, summary="Liveness + corpus inventory")
def health() -> Health:
    """Returns ``ok`` when the process is up, plus a quick view of the loaded corpus."""
    return Health(
        version=VERSION,
        data_root=str(store.DATA_ROOT),
        corpus=store.corpus_stats(),
    )


@app.get("/filings", tags=["filings"], response_model=list[FilingSummary],
         summary="List every filing in the corpus")
def filings() -> list[FilingSummary]:
    """One row per filing with page/block/section counts and OCR share."""
    return [FilingSummary(**row) for row in store.list_filings()]


@app.get("/filings/{stem}", tags=["filings"], response_model=FilingDetail,
         response_model_exclude_none=True, summary="Filing detail and section map")
def filing(stem: str) -> FilingDetail:
    try:
        return FilingDetail(**store.filing_detail(stem))
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/filings/{stem}/sections", tags=["filings"], response_model=list[Section],
         summary="Ordered section spans")
def filing_sections(stem: str) -> list[Section]:
    try:
        return [Section(**row) for row in store.sections(stem)]
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/filings/{stem}/blocks", tags=["filings"], response_model=BlockPage,
         summary="Query provenance blocks")
def filing_blocks(
    stem: str,
    page: int | None = Query(None, ge=1, description="Filter by 1-based page number."),
    block_type: str | None = Query(None, description="Text | Title | List | Table | Figure | Footnote"),
    section: str | None = Query(None, description="Substring match on the section heading."),
    q: str | None = Query(None, description="Substring match inside block text."),
    ocr: bool | None = Query(None, description="Only OCR blocks (true) or only native text (false)."),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> BlockPage:
    try:
        return BlockPage(**store.query_blocks(
            stem, page_number=page, block_type=block_type, section=section, q=q,
            ocr=ocr, offset=offset, limit=limit))
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/filings/{stem}/pages/{page}", tags=["filings"], response_model=PageResponse,
         summary="All blocks on one page")
def filing_page(stem: str, page: int) -> PageResponse:
    try:
        return PageResponse(**store.page(stem, page))
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/filings/{stem}/markdown", tags=["filings"], response_model=MarkdownResponse,
         summary="The filing as section Markdown")
def filing_markdown(stem: str) -> MarkdownResponse:
    try:
        text = store.markdown(stem)
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarkdownResponse(stem=stem, characters=len(text), markdown=text)


@app.get("/filings/{stem}/markdown.txt", tags=["filings"],
         response_class=PlainTextResponse, summary="The filing as raw Markdown text",
         include_in_schema=False)
def filing_markdown_txt(stem: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(store.markdown(stem))
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/tables", tags=["tables"], response_model=list[TableRow],
         summary="Table extraction log")
def tables(
    stem: str | None = Query(None, description="Restrict to one filing."),
    accepted: bool | None = Query(None, description="Only accepted (true) or rejected (false) tables."),
    method: str | None = Query(None, description="lattice | stream | network | pdfplumber"),
    page: int | None = Query(None, ge=1),
    limit: int = Query(500, ge=1, le=5000),
) -> list[TableRow]:
    return [TableRow(**row) for row in
            store.table_log(stem, accepted=accepted, method=method, page_number=page, limit=limit)]


@app.get("/tables/{stem}", tags=["tables"], response_model=list[str],
         summary="Clean grids available for a filing")
def table_names(stem: str) -> list[str]:
    try:
        return store.table_names(stem)
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/tables/{stem}/{name}", tags=["tables"], response_model=TableGrid,
         summary="One clean table as a grid")
def table_grid(stem: str, name: str) -> TableGrid:
    """``name`` is a statement id (e.g. ``income_statement``) or a page/table id
    (e.g. ``p0027_t1``)."""
    try:
        return TableGrid(**store.table_grid(stem, name))
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/xbrl/facts", tags=["xbrl"], response_model=FactsResponse,
         summary="Validated XBRL facts")
def xbrl_facts(
    stem: str | None = None,
    concept: str | None = Query(None, description="Exact us-gaap/... concept name."),
    prefix: str | None = Query(None, description="us-gaap | dei | ..."),
    label: str | None = Query(None, description="Substring match on the human label."),
    q: str | None = Query(None, description="Substring match on concept or label."),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=5000),
) -> FactsResponse:
    return FactsResponse(**store.xbrl_facts(stem, concept=concept, prefix=prefix,
                                            label=label, q=q, offset=offset, limit=limit))


@app.get("/xbrl/comparison", tags=["xbrl"], response_model=list[ComparisonRow],
         summary="PDF values vs XBRL values")
def xbrl_comparison(
    stem: str | None = None,
    statement: str | None = Query(None, description="income_statement | balance_sheet | ..."),
    status: str | None = Query(None, description="match | mismatch | missing_xbrl | ..."),
    path: str | None = Query(None, description="traditional | docling"),
    limit: int = Query(500, ge=1, le=5000),
) -> list[ComparisonRow]:
    return [ComparisonRow(**row) for row in
            store.xbrl_comparison(stem, statement=statement, status=status, path=path, limit=limit)]


@app.get("/xbrl/summary", tags=["xbrl"], response_model=list[XbrlSummaryRow],
         summary="XBRL match rate per statement")
def xbrl_summary() -> list[XbrlSummaryRow]:
    return [XbrlSummaryRow(**row) for row in store.xbrl_summary()]


@app.get("/metrics", tags=["analytics"], response_model=MetricsResponse,
         summary="Evaluation metrics and format sizes")
def metrics() -> MetricsResponse:
    return MetricsResponse(**store.metrics())


@app.get("/benchmarks", tags=["analytics"], response_model=list[TableRow],
         summary="Per-page benchmark timings (Part 10)")
def benchmarks(
    stage: str | None = Query(None, description="parse_pdfplumber | tables | parse_docling | layout"),
    stem: str | None = None,
    limit: int = Query(500, ge=1, le=10000),
) -> list[TableRow]:
    rows = store.benchmarks()
    if stage:
        rows = [r for r in rows if r.get("stage") == stage]
    if stem:
        rows = [r for r in rows if r.get("stem") == stem]
    return [TableRow(**row) for row in rows[:limit]]


@app.get("/search", tags=["analytics"], response_model=SearchResponse,
         summary="Full-text search across the corpus")
def search(
    q: str = Query(..., min_length=1, description="Case-insensitive substring to find."),
    stem: str | None = Query(None, description="Restrict to one filing."),
    limit: int = Query(50, ge=1, le=500),
) -> SearchResponse:
    try:
        return SearchResponse(**store.search(q, stem=stem, limit=limit))
    except store.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.exception_handler(store.NotFound)
def _not_found(_request, exc: store.NotFound):  # pragma: no cover - safety net
    return PlainTextResponse(str(exc), status_code=404)


__all__ = ["app", "Error"]
