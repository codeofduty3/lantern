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
