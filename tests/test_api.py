"""Contract tests for the serving API (src/api).

These run in the smoke job, which installs fastapi/httpx but no pipeline data.
Corpus-dependent assertions skip when ``data/export`` is empty, so the same
file is meaningful locally (after ``dvc pull``) and in CI.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / "data" / "export"
STEMS = sorted(p.stem for p in EXPORT_DIR.glob("*.jsonl")) if EXPORT_DIR.is_dir() else []

client = TestClient(app)
needs_corpus = pytest.mark.skipif(not STEMS, reason="no corpus in data/export (run dvc pull)")


def test_openapi_contract():
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "LANTERN API"
    for required in ("/health", "/filings", "/tables", "/xbrl/facts", "/search"):
        assert required in spec["paths"], required
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            assert "responses" in operation, f"{method.upper()} {path} lacks responses"


def test_swagger_ui_is_served():
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text.lower()


def test_health_reports_corpus():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["corpus"]["filings"] == len(STEMS)


@needs_corpus
def test_filings_and_detail():
    listings = client.get("/filings").json()
    assert listings, "corpus is non-empty but /filings returned nothing"
    stem = listings[0]["stem"]
    detail = client.get(f"/filings/{stem}").json()
    assert detail["stem"] == stem
    assert detail["pages"] >= 1
    assert detail["blocks"] >= 1
    assert [s["section"] for s in detail["section_list"]]


@needs_corpus
def test_blocks_pagination_and_filters():
    stem = STEMS[0]
    first = client.get(f"/filings/{stem}/blocks", params={"limit": 5}).json()
    assert first["total"] >= first["limit"] >= 1
    page = first["items"][0]["page"]
    same_page = client.get(f"/filings/{stem}/blocks",
                           params={"page": page, "limit": 1000}).json()
    assert all(item["page"] == page for item in same_page["items"])


@needs_corpus
def test_search_returns_provenance():
    stem = STEMS[0]
    hits = client.get("/search", params={"q": "the", "stem": stem, "limit": 5}).json()
    assert hits["items"], "every filing contains 'the'"
    hit = hits["items"][0]
    assert hit["stem"] == stem and hit["page"] >= 1 and hit["block_id"]


@needs_corpus
def test_tables_and_grids():
    stem = STEMS[0]
    log = client.get("/tables", params={"stem": stem, "limit": 5}).json()
    assert log
    names = client.get(f"/tables/{stem}").json()
    if names:
        grid = client.get(f"/tables/{stem}/{names[0]}").json()
        assert grid["columns"]
        assert all(len(row) == len(grid["columns"]) for row in grid["rows"])


@needs_corpus
def test_xbrl_and_metrics():
    stem = STEMS[0]
    facts = client.get("/xbrl/facts", params={"stem": stem, "limit": 3}).json()
    assert facts["total"] >= 1
    assert client.get("/xbrl/summary").json()
    metrics = client.get("/metrics").json()
    assert metrics["metrics"]


def test_unknown_filing_is_404():
    assert client.get("/filings/does-not-exist").status_code == 404
