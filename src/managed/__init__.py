"""Part 7 - managed document-AI fallback (AWS Textract), cached by page hash in data/managed/.

With managed.enabled: false (default) only cache hits are used and no API call is ever made,
so dvc repro and CI run without credentials. Keys come from the standard AWS env/profile.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MANAGED, page_pdf_bytes, sha256


def cache_path(page_bytes: bytes) -> Path:
    return MANAGED / f"{sha256(data=page_bytes)}.json"


def analyze_page(pdf_path, pno: int, cfg: dict, force: bool = False):
    """Textract AnalyzeDocument(TABLES) response for one page, or None.
    Returns (response, source) with source in {cache, api, disabled}."""
    page_bytes = page_pdf_bytes(pdf_path, pno)
    cp = cache_path(page_bytes)
    if cp.exists():
        return json.loads(cp.read_text()), "cache"
    if not (cfg.get("enabled") or force):
        return None, "disabled"
    from managed.textract import analyze  # lazy: boto3 only needed when enabled
    resp = analyze(page_bytes, cfg)
    MANAGED.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(resp))
    return resp, "api"
