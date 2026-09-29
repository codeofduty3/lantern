"""Part 5 - provenance schema (Appendix B), validated on every write."""
import json
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "lantern/1.0"
BlockType = Literal["Text", "Title", "List", "Table", "Figure", "Footnote"]


class TableObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: List[str]
    rows: List[list]            # normalized values, one row per (section, label)
    raw_cells: List[List[str]]  # extractor grid as-is
    scale: float


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: str = Field(SCHEMA_VERSION, alias="schema")
    doc_id: str
    company: str
    cik: str
    ticker: str
    form: str
    fiscal_year: int
    fiscal_period: str
    page: int = Field(ge=1)
    section: Optional[str] = None
    block_id: str
    block_type: BlockType
    bbox: List[float]
    units: Literal["pt"] = "pt"
    origin: Literal["top-left"] = "top-left"
    text: Optional[str] = None
    table: Optional[TableObj] = None
    extractor: str
    extractor_version: str
    ocr: bool = False
    ocr_conf: Optional[float] = None
    source_path: str
    sha256: str

    @field_validator("doc_id")
    @classmethod
    def accession(cls, v):
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", v):
            raise ValueError(f"doc_id must be an accession number, got {v!r}")
        return v

    @field_validator("cik")
    @classmethod
    def cik10(cls, v):
        if not re.fullmatch(r"\d{10}", v):
            raise ValueError("cik must be zero-padded to 10 digits")
        return v

    @field_validator("bbox")
    @classmethod
    def box(cls, v):
        if len(v) != 4 or v[0] > v[2] or v[1] > v[3]:
            raise ValueError(f"bbox must be [x0, top, x1, bottom], got {v}")
        return v


def write_jsonl(records, path):
    """Validate every record on write; a bad field fails the stage that produced it."""
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(Record(**r).model_dump_json(by_alias=True) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
