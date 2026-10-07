"""Pydantic response models -- these are what Swagger renders and validates."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Loose(BaseModel):
    """Base model that keeps unknown fields so pipeline columns survive verbatim."""

    model_config = ConfigDict(extra="allow")


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "lantern-api"
    version: str
    data_root: str
    corpus: dict[str, Any]


class FilingSummary(BaseModel):
    stem: str = Field(examples=["AKAM_10K_20241231"])
    doc_id: Optional[str] = None
    company: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    form: Optional[str] = Field(default=None, examples=["10-K"])
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    pages: int = 0
    blocks: int = 0
    sections: int = 0
    tables: int = 0
    ocr_blocks: int = 0
    ocr_share: float = 0.0
    markdown_chars: int = 0
    source_path: Optional[str] = None
    sha256: Optional[str] = None


class Section(Loose):
    section: str
    first_page: Optional[int] = None
    last_page: Optional[int] = None
    blocks: int


class FilingDetail(FilingSummary):
    section_list: list[Section] = []
    pages_list: list[int] = []
    table_count: int = 0
    xbrl_facts: int = 0


class Block(Loose):
    block_id: str
    page: int
    block_type: str
    section: Optional[str] = None
    text: Optional[str] = None
    bbox: Optional[list[float]] = None


class BlockPage(BaseModel):
    stem: str
    total: int
    offset: int
    limit: int
    items: list[Block]


class PageResponse(BaseModel):
    stem: str
    page: int
    blocks: list[Block]
    text: str


class MarkdownResponse(BaseModel):
    stem: str
    characters: int
    markdown: str


class TableRow(Loose):
    stem: Optional[str] = None
    page: Optional[Any] = None
    table: Optional[Any] = None
    method: Optional[str] = None
    accepted: Optional[bool] = None


class TableGrid(BaseModel):
    stem: str
    table: str
    columns: list[str]
    rows: list[list[Optional[str]]]


class Fact(Loose):
    stem: str
    concept: str
    label: Optional[str] = None
    value: Optional[str] = None
    value_num: Optional[float] = None


class FactsResponse(BaseModel):
    total: int
    offset: int
    limit: Optional[int] = None
    items: list[Fact]


class ComparisonRow(Loose):
    stem: str
    statement: Optional[str] = None
    label: Optional[str] = None
    period: Optional[str] = None
    status: Optional[str] = None
    pdf_value: Optional[str] = None
    xbrl_value: Optional[str] = None


class XbrlSummaryRow(Loose):
    stem: Optional[str] = None
    path: Optional[str] = None
    statement: Optional[str] = None
    matched: int
    mismatch: int
    total: int
    match_rate: Optional[float] = None


class SearchHit(Loose):
    stem: str
    page: Optional[int] = None
    block_id: Optional[str] = None
    block_type: Optional[str] = None
    section: Optional[str] = None
    snippet: str


class SearchResponse(BaseModel):
    query: str
    total: int
    truncated: bool = False
    items: list[SearchHit]


class MetricsResponse(BaseModel):
    metrics: dict[str, Any]
    format_sizes: list[dict[str, Any]]
    xbrl_summary: list[XbrlSummaryRow]
    reports: list[dict[str, Any]]


class Error(BaseModel):
    detail: str
