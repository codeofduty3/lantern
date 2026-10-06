# Docling vs traditional pipeline

<!-- AUTO:START (generated, do not edit) -->
| dimension | traditional | docling | source |
|---|---|---|---|
| WER (mean) | - | - | eval.md |
| CER (mean) | - | - | eval.md |
| numeric accuracy | - | - | eval.md |
| table cell F1 | 0.947 | 1.000 | eval.md |
| XBRL match rate | 0.891 | 0.922 | xbrl.md |
| s/page p50 | - (text) / - (tables) / - (layout) | - | benchmarks.md |
| provenance | page + bbox per block (layout) | page + bbox per item (prov.jsonl, normalized to top-left) | data/export, data/docling |

Rendered PDF vs original iXBRL HTML (Docling), data/docling/html_vs_pdf.csv:

| metric         |   rendered_pdf | original_html           |
|:---------------|---------------:|:------------------------|
| tables         |             81 | 89                      |
| numeric_cells  |           1619 | 5259                    |
| markdown_chars |         493654 | 1012328                 |
| pages          |             97 | n/a (HTML has no pages) |
<!-- AUTO:END -->

## Discussion

Footnotes audit (5 notes pages), reading-order examples, and the one-paragraph recommendation to Lina: primary path and fallback.

### Scanned fixture backend

The scanned fixture (`tests/fixtures/scanned.pdf`) is converted with Docling's `pypdfium2`
backend (`docling.scanned_backend` in `params.yaml`) on every platform. The default
`docling_parse` backend segfaults in its native parser on that rasterized, image-only PDF
on Intel macOS (x86_64); the crash reproduces with OCR and table structure both disabled,
so it is the file plus that platform build rather than the OCR engine. The rendered
filings keep the default backend, so no other Docling output is affected. One backend is
used everywhere because `dvc.lock` records a single hash for `data/docling`: a
per-platform backend would leave that lock valid on only one platform.

Measured effect: the same fixture converted with the default backend on Linux
(docling-parse 7.22.0) and with `pypdfium2` here (7.22.1) gives 3 pages and 1 table in both
cases, and 14,426 vs 14,409 characters (126 vs 124 lines) — 17 characters, 0.12%. For
scale, the ceiling this project sets for scanned text is `tests.max_wer_scanned` (15%), and
the pipeline's two OCR paths disagree by 9.5%, 0.2% and 33.1% word-level on those same
three pages.

Two caveats stay on the record. That comparison changes backend and docling-parse patch
version at once, so the 17 characters are not attributed to either one — swapping only the
backend on the Linux machine, or diffing the two `scanned.md` files, settles it. And the
scanned fixture feeds no scored metric (its ground truth is not transcribed), so the
deviation moves no number in `reports/metrics.json`.
