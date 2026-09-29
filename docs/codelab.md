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
Duration: 4

One JSONL record and its Markdown line with the provenance comment.

## Part 6 - Storage formats
Duration: 3

Sizes, token counts, LLM answers, format decision.

## Part 7 - Build vs buy
Duration: 4

Textract vs open source side by side; cost; fallback design.

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
Duration: 5

Match rate per statement and path; one diagnosed mismatch.
