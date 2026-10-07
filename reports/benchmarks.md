# Cost and throughput benchmarks

<!-- AUTO:START (generated, do not edit) -->
Machine: macOS-26.5.2-x86_64-i386-64bit; i386; 8 cores / 16 threads; 64.0 GB RAM; Python 3.11.17

| Stage | Pages | s/page p50 | s/page p95 | Peak RSS MB | Empty/errors | Notes |
|---|---|---|---|---|---|---|
| layout | 100 | 0.502 | 0.582 | 1946 | 1 | cold first page 4.79s |
| parse_docling | 100 | 1.590 | 7.352 | 2575 | 1 | cold first page 14.55s |
| parse_pdfplumber | 100 | 0.370 | 0.610 | 1047 | 0 | cold first page 0.24s |
| tables | 45 | 1.012 | 1.730 | 1601 | 0 | cold first page 2.75s |

Annual sequential runtime estimate: traditional 184.4 h/year; Docling 220.8 h/year. EDGAR download is capped at 10 requests/s (~16.7 min of requests for 5,000 filings at ~2 requests each).

| path | USD / 1,000 pages | USD / year | assumptions |
|---|---:|---:|---|
| traditional stages on 8-vCPU cloud VM (assumption) | 0.15 | 74 | 1.328 s/page; $0.4/h; 100 pages/filing; engineering time excluded; table stage weighted by 45% candidate-page share |
| Docling alternate on 8-vCPU cloud VM (assumption) | 0.18 | 88 | 1.590 s/page; $0.4/h; 100 pages/filing; engineering time excluded |
| managed: textract_text | 1.50 | 750 | list price, first tier (aws.amazon.com/textract/pricing) |
| managed: textract_tables | 15.00 | 7,500 | list price, first tier (aws.amazon.com/textract/pricing) |
<!-- AUTO:END -->

## Discussion

Bottleneck stages, CPU vs GPU recommendation, concurrency (process pool per stage, EDGAR limit), and the crossover volume vs the managed service.
