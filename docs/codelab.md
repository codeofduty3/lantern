summary: Project LANTERN - financial report parsing pipeline
id: lantern-case-study-1
categories: data-engineering
environments: Web
tags: dvc, pdf, xbrl
status: Published
authors: codeofduty3

# Project LANTERN: from EDGAR filings to a validated corpus

## Overview
Duration: 2

Turn two Akamai filings (one 10-K, one 10-Q) into a layout-aware, XBRL-validated corpus:
Markdown + JSONL with page/bbox provenance, versioned end to end with DVC. The DAG runs
download -> render -> parse_pdfplumber / tables / layout / parse_docling -> export + xbrl ->
evaluate, then a serving layer over the artifacts. The architecture diagram and the
Part-by-Part map to code and reports are in the README.

## Part 0 - Download and render
Duration: 5

```bash
dvc repro download render
```

Pinned in `params.yaml`: AKAM, one 10-K and one 10-Q inside 2024-01-01..2026-01-01. Download
fetches the EDGAR submissions plus the iXBRL (`.xsd` + linkbases); render prints each filing to
a Letter PDF with headless Chromium. Evidence: `data/rendered/manifest.csv` (stem, accession,
CIK, sha256, renderer) - 2 filings, 97 and 63 pages.

## Part 1 - Text extraction with OCR fallback
Duration: 5

pdfplumber reads the text layer; a page routes to Tesseract only when a trigger fires
(`ocr.min_chars: 100`, `junk_ratio: 0.2`, `image_area: 0.6`). Calibration is in
`reports/ocr_calibration.md`: the native pages carry at least 334 chars, so any cutoff from 2
to 334 makes the same decision (100 is a conservative choice inside the gap), and 200 DPI gave
the lowest WER (`--oem 1 --psm 6`). Of the 160 filing pages, 159 stay on the text layer and one
(10-Q page 2) routes to OCR; the three scanned fixture pages all route to OCR. Evidence:
`data/parsed/ocr_log.csv` (reason, chars, junk_ratio, image_ratio, OCR confidence per page).

## Part 2 - Tables and the hybrid extractor
Duration: 5

```bash
python src/bakeoff.py       # Camelot lattice/stream/network vs pdfplumber, one normalizer
```

Each table-candidate page is extracted with every method; the winner is the highest
`accuracy - 0.5*whitespace` above a coverage floor (`tables.accept_score: 80`,
`min_coverage: 0.6`). The winner depends on table type - on the 10-K income statement, stream
and network both reach 100% number coverage while lattice reaches 73% - and no single method
wins everywhere: stream is the most common winner, lattice takes equity, and network takes 22
of the "other table" pages. Evidence: `reports/tables_method.md`,
`data/tables/tables_log.csv`, clean grids in `data/tables/*.clean.csv`.

## Part 3 - Layout detection and routing
Duration: 5

EfficientDet (PubLayNet) labels every region - Title, Text, List, Table, Figure - and assigns
reading order, including multi-column pages; the label routes the block (body text to
pdfplumber, tables to Camelot). Box overlays for the 10 audited pages are in `reports/layout/`.
Audit numbers (`reports/layout_audit.md`): Text precision/recall 0.91, Title 1.00, Table 0.83 -
one missed box and one mistyped box, the weakest class, which is exactly why tables get a
dedicated extractor and an XBRL cross-check. Multi-column reading-order WER is 0.000.

## Part 4 - Docling
Duration: 5

The same corpus through Docling, scored against the Part 9 ground truth
(`reports/docling_comparison.md`). Docling leads on the gold statement tables (cell F1 1.000 vs
0.947) and XBRL match rate (0.922 vs 0.919); our pipeline leads on text (WER 0.028 vs 0.154,
CER 0.017 vs 0.128), the footnote stratum (0.002 vs 0.229), and speed (layout p50 0.641 s/page
vs 3.050). Decision: keep the traditional layout-aware pipeline primary, Docling as the
table-focused fallback. Rendering also loses content - the rendered PDF yields 82 tables and
1,487 numeric cells vs 89 and 2,788 in the original iXBRL HTML.

## Part 5 - Metadata and provenance
Duration: 4

Every block is one JSONL record carrying the filing identity, page, section, `block_type`,
`bbox`, extractor, OCR flag and source hash, validated against `src/schema.py` (`lantern/1.0`).
The Markdown export repeats the provenance as an HTML comment.

Record shape from `data/export/AKAM_10K_20241231.jsonl` (fields trimmed):

```json
{"schema":"lantern/1.0","doc_id":"0001086222-25-000028","ticker":"AKAM","form":"10-K",
 "page":1,"section":"FORM 10-K","block_id":"p0001_b001","block_type":"Title",
 "bbox":[263.14,112.24,348.07,130.74],"origin":"top-left","text":"FORM 10-K",
 "extractor":"pdfplumber","ocr":false,"sha256":"4a433d25...e697"}
```

```markdown
<!-- 0001086222-25-000028 p1 p0001_b001 -->
### FORM 10-K
```

## Part 6 - Storage formats
Duration: 3

`reports/format_decision.md` holds the sizes and token counts: relative to TXT, Markdown costs
about 1.4-1.5x the tokens and JSONL about 2.3x. In an LLM retrieval test (AKAM 10-Q, three
value-plus-page questions, a fresh chat per format) all three formats returned the right
values, but only Markdown and JSONL could cite the PDF page - TXT carries no provenance.
Decision: JSONL is the source of truth (bbox + schema), Markdown feeds Case Study 2 (page
cites at 67% of the tokens), TXT is a baseline only.

## Part 7 - Build vs buy
Duration: 4

One clean statement page and one scanned page, our stack against AWS Textract
(`reports/build_vs_buy.md`). pdfplumber matched the clean page's text layer exactly (WER
0.0000) vs Textract 0.0052; on the scanned page Textract leads (0.0052 vs Tesseract 0.0155) and
found a table we missed, but only 38 cells matched exactly with 21 unmatched rows on each side.
At $0.0150/page, `AnalyzeDocument(TABLES)` on the configured 500k pages/year is about
$7,500/year. `managed.enabled: false` stays the default; live calls only after the residency,
retention and training-use questions in the report are answered in writing.

```bash
python src/managed/compare.py              # page-hash cache, no API calls
python src/managed/compare.py --call-api   # populate the cache (2 Textract requests)
dvc add data/managed
```

## Part 8 - DVC pipeline and CI
Duration: 4

`dvc.yaml` defines the DAG (`dvc dag` to view it). Data - raw, rendered, parsed, layout,
docling, xbrl, ground truth and the managed cache - is DVC-tracked on the shared S3 remote, so
`dvc repro` is idempotent: the first run restores or reruns, the second skips every stage. The
`layout` stage is frozen (its Colab-only stack) and restored by `dvc pull`. CI
(`.github/workflows/smoke.yml`) runs offline on every PR against the committed fixtures - no
EDGAR, no DVC remote, no credentials. Evidence: `dvc.lock`, green smoke run.

## Part 9 - Evaluation
Duration: 4

```bash
dvc repro evaluate
dvc metrics diff
```

`src/evaluate.py` scores WER/CER/numeric accuracy per page and stratum, table cell P/R/F1, and
the XBRL match rate into `reports/metrics.json` and `reports/eval.md`. Corpus result:
traditional text WER 0.028 / CER 0.017, table cell F1 0.947, XBRL match rate 0.919. Regression
tests (`tests/test_quality.py`) fail on drift against the `tests:` thresholds in `params.yaml`
(`max_wer_text: 0.10`, `max_wer_scanned: 0.15`, `min_cell_f1: 0.90`); we proved they have teeth
by breaking the multi-column extractor and watching `test_text_wer[multicol-1-0.1]` fail
(`1.0 <= 0.1`). Drift plot: `reports/plots/drift.png`.

## Part 10 - Benchmarks
Duration: 3

```bash
python src/bench.py
```

Run separately because timings are hardware-dependent: a fresh process per stage, up to 100
pages (75 table-candidate pages). Warm p50 - text 0.016 s/page, layout 0.641, tables 1.182,
Docling 3.050; cold first page - layout 8.96 s, Docling 20.68 s. Layout peaks near 3.4 GB, so
concurrency is capped at 6 workers under a 70% RAM budget. Cost is about $0.13 per 1,000 pages
(~$67/year) for the traditional stages and $0.34 (~$169/year) for Docling on the assumed
8-vCPU/32-GiB VM. Report: `reports/benchmarks.md`.

## Part 11 - XBRL validation
Duration: 5

`src/xbrl.py` maps each statement line to a `us-gaap` concept with `config/label_map.yaml`, then
compares the PDF value to the fact from the filing's own iXBRL (`data/xbrl/facts.csv`,
`data/xbrl/comparison.csv`). Match rates (`reports/xbrl.md`): traditional balance sheet 97.3%
and income statement 87.5%; Docling 98.9% / 87.5%. Diagnosed case - `InterestExpenseNonoperating`
differs only in sign, because the PDF prints a negative presentation value while the XBRL fact
is positive; we classify it `sign` and keep both source values rather than silently flipping it.
Caption fragments that are not monetary statement rows are excluded from the denominator and
reported for audit.

## Part 12 - Serving layer (API + UI)
Duration: 4

```bash
make api     # FastAPI + Swagger at http://127.0.0.1:8000/docs
make ui      # Streamlit at http://127.0.0.1:8501
```

A read-only FastAPI backend serves the corpus as JSON - filings, provenance blocks, Markdown,
tables, XBRL facts, search, metrics and benchmarks - with runnable Swagger at `/docs`; the
Streamlit frontend browses the same data in tabs. Show `/health`, run one `/search` with
**Try it out**, then the explorer. `make bundle` freezes a portable `data/serve` for Replit or
Vercel; deployment notes are in `docs/serving.md`.
