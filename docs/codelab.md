summary: Project LANTERN - financial report parsing pipeline
id: lantern-case-study-1
categories: data-engineering
tags: dvc, pdf, xbrl
status: Published
authors: codeofduty3

# Project LANTERN: from EDGAR filings to a validated corpus

## Overview
Duration: 2

What we build, the architecture diagram, and what each stage outputs.

## Part 0 - Download and render
Duration: 5

```bash
dvc repro download render
```

Screenshot: `data/rendered/manifest.csv` and one rendered page.

## Part 1 - Text extraction with OCR fallback
Duration: 5

Trigger signals, thresholds (evidence from Exercise 1a/1b), `ocr_log.csv` excerpt.

## Part 2 - Tables and the hybrid extractor
Duration: 5

`python src/bakeoff.py`; bake-off table and the winning method per table type.

## Part 3 - Layout detection and routing
Duration: 5

QA overlay screenshot; multi-column reading order; audit table.

## Part 4 - Docling
Duration: 5

Comparison table (WER, cell F1, XBRL match rate, throughput) and recommendation.

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

![Page 13 of the 10-K with block p0013_b002 boxed](img/part5_bbox.png)

All 811 records validate, both filings have the same fields, and every Markdown line leads back to a page and a box.

## Part 6 - Storage formats
Duration: 2

We save the same content as JSONL, Markdown and plain text, and compare their size.

```bash
cat data/export/format_sizes.csv
```

![format_sizes.csv for both filings](img/part6_format_sizes.png)

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

`dvc dag`, `dvc repro` twice, green smoke CI run.

## Part 9 - Evaluation
Duration: 4

Metrics, failing-test run, drift plot, `dvc metrics diff`.

## Part 10 - Benchmarks
Duration: 3

`python src/bench.py`; seconds/page, RSS, cost per 1,000 pages.

## Part 11 - XBRL validation
Duration: 4

We check the numbers our pipeline read from the PDF tables against the filing's own XBRL tags, which Arelle reads for us.

```bash
dvc repro xbrl
dvc metrics show
```

![reports/metrics.json with the XBRL match rates](img/part11_metrics.png)

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

`uvicorn src.api.main:app` serves the corpus as JSON with Swagger at `/docs`;
`streamlit run app/streamlit_app.py` is the browser UI. Show `/health`, run one
`/search` from the Swagger **Try it out** button, then the Streamlit explorer.
Deployment (Replit API, Vercel API, Streamlit Cloud UI) is in `docs/serving.md`.
