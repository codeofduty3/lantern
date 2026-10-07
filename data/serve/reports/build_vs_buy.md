# Build vs buy: managed document AI

<!-- AUTO:START (generated, do not edit) -->
| page | source | open-source engine | managed | WER open source | WER managed | managed-vs-open-source WER | reference | table cells: both equal / differ / only OSS / only managed |
|---|---|---|---|---:|---:|---:|---|---|
| clean_statement | AKAM_10K_20241231.pdf p53 | pdfplumber; tables=stream | textract (cache, conf 99.8) | 0.0 | 0.0052 | 0.0052 | pdfplumber text layer | 38 / 1 / 21 / 21 |
| scanned_statement | scanned.pdf p3 | tesseract; tables=none | textract (cache, conf 99.7) | 0.0155 | 0.0052 | 0.0206 | ground truth | 0 / 0 / 0 / 60 |

Text comparison files: `reports/managed/*_text.txt`; table-cell comparisons: `reports/managed/*_cells.csv`; schema-mapped managed records: `reports/managed/*.jsonl`.

Public AWS list-price reference: [Amazon Textract pricing](https://aws.amazon.com/textract/pricing/) (US West/Oregon, first 1M pages/month; rates vary by Region and volume). `DetectDocumentText` is $0.0015/page; this pipeline instead calls `AnalyzeDocument(TABLES)` at $0.0150/page. Do not add the two prices: the table-enabled call returns text and table blocks in one request.

| configured workload | pages / year | estimated USD / year |
|---|---:|---:|
| `AnalyzeDocument(TABLES)` on every page | 500,000 | 7,500 |

Estimate uses the configured volume and the public first-tier US West reference price; it is not an AWS quote.
<!-- AUTO:END -->

## Discussion

### Results and recommendation

Keep Textract disabled by default. On the clean income-statement page, pdfplumber matched its text-layer reference exactly (WER 0.0000); Textract had WER 0.0052. The normalized table comparison found 38 equal and 1 differing cells among matched row/period keys, plus 21 unmatched rows on each side, so table labels and coverage still need reconciliation before managed output can replace the local parser. Against the manually transcribed scanned-page ground truth, Tesseract had WER 0.0155 and Textract WER 0.0052; both preserved all numeric tokens. The open-source table extractor found no table there while Textract did; this supports using it as a targeted fallback, not claiming a proven table accuracy win.

Keep `managed.enabled: false` for routine runs. If client approval and data controls permit live requests, enable the fallback only for low OCR confidence (`ocr.managed_below_conf`) or low table quality (`tables.managed_below_score`); cache hits remain usable with the fallback disabled. Reconcile unmatched table labels before broadening its use.

### Client-document data handling

Before sending client documents, obtain answers and written approval for:

- **Region and residency:** Where are request bytes and results processed? Does the configured `us-east-1` endpoint meet the client's residency and cross-border requirements?
- **Retention and logging:** Are synchronous input bytes, output, or diagnostic data retained, for how long, and can support or audit logs contain document content? Define deletion and incident-response requirements.
- **Training and human access:** Are document inputs or outputs used to train, improve, or evaluate models, or reviewed by people? Can those uses be disabled contractually?
- **Protection and local cache:** Confirm encryption and key-control requirements, access controls, and whether the DVC remote and local `data/managed/` cache meet the client's retention and access policies. The cache contains extracted document content, not just opaque hashes.

AWS documents TLS transport and shared-responsibility controls in its [Textract data-protection guidance](https://docs.aws.amazon.com/textract/latest/dg/data-protection.html); those facts do not answer the client-specific retention, training-use, residency, or contractual questions above. Do not enable live calls until those questions are resolved.
