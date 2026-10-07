# Cost and throughput benchmarks

<!-- AUTO:START (generated, do not edit) -->
Machine / hardware: macOS-26.5.2-x86_64-i386-64bit; i386; 8 cores / 16 threads; 64.0 GB RAM; Python 3.11.17

| Stage | Pages | s/page p50 | s/page p95 | Peak RSS MB | Failures | Notes |
|---|---:|---:|---:|---:|---|---|
| parse_pdfplumber | 100 | 0.016 | 0.027 | 1599 | 0 empty, 0 exceptions | no model cold start; 160 eligible candidates in 160 pages |
| tables | 75 | 1.182 | 2.581 | 2138 | 0 empty, 0 exceptions | no model cold start |
| layout | 100 | 0.641 | 0.968 | 3437 | 2 empty, 0 exceptions | cold first page 8.96s; 160 eligible candidates in 160 pages |
| parse_docling | 100 | 3.050 | 7.883 | 2962 | 1 empty, 0 exceptions | cold first page 20.68s; 160 eligible candidates in 160 pages |

| path | USD / 1,000 pages | USD / year | assumptions |
|---|---:|---:|---|
| traditional stages on 8-vCPU/32-GiB CPU-only cloud VM (assumption) | 0.13 | 67 | 1.211 s/page; $0.4/h; 100 pages/filing; download, render, export, XBRL, engineering, storage and egress excluded; us-east-1 on-demand price assumption ([EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/)); tables weighted by 46.9% candidate-page share |
| Docling alternate on 8-vCPU/32-GiB CPU-only cloud VM (assumption) | 0.34 | 169 | 3.050 s/page; $0.4/h; 100 pages/filing; download, render, export, XBRL, engineering, storage and egress excluded; us-east-1 on-demand price assumption ([EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/)) |
| managed: textract_text | 1.50 | 750 | list price, first tier, us-east-1 (https://aws.amazon.com/textract/pricing/) |
| managed: textract_tables | 15.00 | 7,500 | list price, first tier, us-east-1 (https://aws.amazon.com/textract/pricing/) |

p50/p95 use warm pages for model stages and all non-exception pages otherwise; RSS is sampled during each page call. Annual measured-stage sequential runtime: traditional 168.2 h/year; Docling 423.6 h/year. EDGAR download is capped at 10 requests/s (~16.7 min of requests for 5,000 filings at ~2 requests each).

Measured traditional-path bottleneck: layout at 0.641 weighted s/page.
Hardware/concurrency: CPU-first; no GPU timing was collected. GPU comparison assumption is $1.2/h, not a measured quote ([EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/)); consider a GPU only if layout is the bottleneck and a measured speedup offsets its hourly premium. For the assumed 8-vCPU/32-GiB VM, use at most 6 workers under a 70% RAM budget, based on the measured layout process peak (3.36 GiB); benchmark scaling because model weights are duplicated per worker.
Download concurrency: enforce a shared EDGAR-wide rate limiter at no more than 10 requests/second ([SEC access guidance](https://www.sec.gov/os/accessing-edgar-data)); downstream processing may use its own bounded worker pool.
Managed-service crossover: open-source figures are compute-only; engineering, storage, and egress are excluded. Solve fixed engineering cost / per-page variable savings for a break-even volume and compare equivalent service coverage.
<!-- AUTO:END -->

## Discussion

Use the generated recommendation as a measured starting point, not a substitute for a
throughput-scaling or GPU comparison. Compare managed pricing only for equivalent functionality;
open-source figures exclude engineering and other non-compute costs.
