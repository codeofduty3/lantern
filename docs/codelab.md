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

Screenshot: `data/rendered/manifest.csv` and one rendered page.

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
Duration: 3

Every block we extract is saved as a JSONL record that says where it came from. Each record must pass the schema in `src/schema.py` before it's written, so bad data stops the stage instead of slipping through.

```bash
dvc repro export
head -c 400 data/export/AKAM_10K_20241231.jsonl
```

A record from the 10-K:

```json
{
  "doc_id": "0001086222-25-000028",
  "cik": "0001086222",
  "form": "10-K",
  "fiscal_year": 2024,
  "fiscal_period": "FY",
  "page": 13,
  "section": "Item 1A. Risk Factors",
  "block_id": "p0013_b002",
  "bbox": [0.85, 368.0, 560.89, 387.01],
  "text": "Defects or disruptions in our products and IT systems could require us to increase spending ...",
  "extractor": "pdfplumber"
}
```

The section comes from the 10-K's "Item N." headings, read from every line of the PDF so headings the layout model missed still count.

The Markdown file carries the same address in a comment:

```markdown
<!-- 0001086222-25-000028 p13 p0013_b002 -->
Defects or disruptions in our products and IT systems could require us to increase spending ...
```

All 811 records validate, both filings have the same fields, and every Markdown line leads back to a page and a box.

## Part 6 - Storage formats
Duration: 2

We save the same content as JSONL, Markdown and plain text, and compare their size.

```bash
cat data/export/format_sizes.csv
```

| format | approx. tokens, 10-K | vs TXT |
|---|---|---|
| txt | 67,205 | 1.0x |
| md | 96,311 | 1.43x |
| jsonl | 159,585 | 2.37x |

We asked ChatGPT three questions about the 10-Q in each format. All three got the numbers right, but only Markdown and JSONL could give the correct page.

JSONL is our source of truth because it keeps every field. Markdown feeds Case Study 2 because it keeps the page labels at far fewer tokens. Details are in `reports/format_decision.md`.

## Part 7 - Build vs buy
Duration: 4

Compare the clean and scanned statement pages in `reports/build_vs_buy.md`, including text and
table-cell outputs under `reports/managed/`. The script reads page-hash cache entries by default:

```bash
python src/managed/compare.py
```

To populate the cache, explicitly allow the two Textract requests:

```bash
python src/managed/compare.py --call-api
dvc add data/managed
```

Review the provider pricing and client-document data-handling questions in the report before
enabling live calls. `managed.enabled: false` remains the default; DVC stages can use cache hits
but make no API calls when the cache misses.

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
Duration: 4

We check the numbers our pipeline read from the PDF tables against the filing's own XBRL tags, which Arelle reads for us.

```bash
dvc repro xbrl
dvc metrics show
```

Each table row is matched to an XBRL concept using our dictionary first, then the filing's own labels, then fuzzy matching. Then the values are compared.

| path | statement | matched / compared | rate |
|---|---|---|---|
| traditional | balance_sheet | 107 / 110 | 97.3% |
| traditional | income_statement | 119 / 136 | 87.5% |
| docling | balance_sheet | 93 / 94 | 98.9% |
| docling | income_statement | 119 / 136 | 87.5% |

Most of what's left is a sign convention, not an error: the statement shows an expense as `(27,117)`, while XBRL stores it as a positive number.

One fix: "Other expense, net" failed on the 10-Q because Akamai tagged it with a different concept than in the 10-K. Letting the search fall back to the filing's own labels fixed it without touching the dictionary. Every remaining mismatch is explained in `reports/xbrl.md`.

## Part 12 - Serving layer (API + UI)
Duration: 4

```bash
make serve-venv   # one-time: isolated venv for the serving deps
make api          # backend  -> http://127.0.0.1:8000/docs
make ui           # frontend -> http://127.0.0.1:8501
make test-api     # API contract tests
```

`make api` wraps `uvicorn src.api.main:app` and `make ui` wraps
`streamlit run app/streamlit_app.py`. The backend serves the corpus as JSON with
Swagger at `/docs`; show `/health`, run one `/search` from the Swagger **Try it
out** button, then the Streamlit explorer. `make bundle` freezes the portable
`data/serve` bundle, and deployment (Replit API, Vercel API, Streamlit Cloud UI)
is in `docs/serving.md`.
