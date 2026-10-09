# Docling vs traditional pipeline

<!-- AUTO:START (generated, do not edit) -->
| dimension | traditional | docling | source |
|---|---|---|---|
| WER (mean) | 0.028 | 0.154 | eval.md |
| reading-order WER (multi-column stratum) | 0.000 | 0.000 | eval.md; tests/fixtures/gt/CONVENTIONS.md |
| footnote-text WER | 0.002 | 0.229 | eval.md; requires footnote ground-truth stratum |
| CER (mean) | 0.017 | 0.128 | eval.md |
| numeric accuracy | 0.953 | 0.898 | eval.md |
| table cell F1 | 0.947 | 1.000 | eval.md |
| XBRL match rate | 0.919 | 0.922 | xbrl.md |
| s/page p50 | 0.016 (text) / 1.182 (tables) / 0.641 (layout) | 3.050 | benchmarks.md |
| Part 10 coverage | text: 100 pages; 100 non-empty; 0 empty; 0 errors; tables: 75 pages; 75 non-empty; 0 empty; 0 errors; layout: 100 pages; 98 non-empty; 2 empty; 0 errors | 100 pages; 99 non-empty; 1 empty; 0 errors | data/bench/*.csv |
| provenance | page + bbox per block (layout) | page + bbox per item (prov.jsonl, normalized to top-left) | data/export, data/docling |

WER by stratum (reading order shows on multi-column pages):

| stratum              |   docling |   traditional |
|:---------------------|----------:|--------------:|
| contents             |    0.1575 |        0.0282 |
| cover                |    0.2111 |        0.0778 |
| dense_notes          |    0.0737 |        0.0206 |
| dense_notes_footnote |    0.2288 |        0.0024 |
| exhibit              |    0.1196 |        0.0036 |
| multi-column         |    0      |        0      |
| prose                |    0.2755 |        0.0112 |
| scanned              |    0.1495 |        0.0155 |
| statement            |    0.0945 |        0.0527 |

Rendered PDF vs original iXBRL HTML (Docling), data/docling/html_vs_pdf.csv:

| metric         |   rendered_pdf | original_html           |
|:---------------|---------------:|:------------------------|
| tables         |             82 | 89                      |
| numeric_cells  |           1487 | 2788                    |
| markdown_chars |         492985 | 1012018                 |
| pages          |             97 | n/a (HTML has no pages) |
<!-- AUTO:END -->

## Discussion

### Measured comparison and coverage

The Part 9 ground truth now covers both tables and text. On the gold statement tables,
Docling's cell F1 is **1.000** versus **0.947** for the traditional extractor (188 gold
cells across the 10-K statement pages and fixture), and its XBRL match rate is **0.922**
versus **0.919**. Those results favor Docling for statement-table recovery, but they do
not establish better table geometry.

Text flips the ranking. Across the 22 transcribed pages in `data/ground_truth/strata.csv`
(twenty filing pages -- one per stratum per filing -- plus the scanned and multi-column
fixtures), the traditional parser scores mean WER **0.028** / CER **0.017** / numeric
accuracy **0.953**, against Docling's **0.154** / **0.128** / **0.898**. The footnote
stratum is the widest gap, **0.002** versus **0.229**, and reading order on the
multi-column fixture is a **0.000** tie. The sample is one page per stratum, so read the
means as directional rather than exhaustive.

Both paths expose page and bounding-box provenance: traditional blocks in `data/layout/`
and exported records, and Docling item provenance in per-filing `.prov.jsonl` files using
top-left point coordinates. On the Part 10 sample (100 pages for text/layout/Docling, 75
table-candidate pages), warm p50 was 0.016 s/page for traditional text, 0.641 for layout,
and 1.182 on tables; Docling was 3.050 s/page. Weighting the table stage by its 46.9%
candidate-page share gives an estimated 1.211 s/page for traditional sequential stages
versus 3.050 for Docling; this is a stage-median estimate, not a separately instrumented
end-to-end run. Layout returned two empty results (the blank 10-Q pages 2 and 7) and
Docling one (10-Q page 2), with no runtime exceptions. The HTML/PDF comparison shows 82
vs 89 detected tables and 1,487 vs 2,788 normalized numeric cells, respectively, plus
492,985 vs 1,012,018 Markdown characters. This isolates substantial content
loss/compaction during rendering, but HTML has no pagination and the counts do not by
themselves imply better structural accuracy.

### Recommendation to Lina

Keep the traditional layout-aware pipeline as the primary corpus path and Docling as the
table-focused alternate/fallback for now. The traditional sequential stage estimate is
faster (1.211 vs 3.050 s/page), and it leads on text WER/CER, numeric accuracy and the
footnote stratum, while Docling leads on the gold table-cell F1 and XBRL match rate. The
two paths tie on the single multi-column reading-order fixture. Revisit the primary-path
choice if broader text ground truth moves the footnote or reading-order result, or once
the table-weighted throughput estimate is validated end-to-end.

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
scanned fixture is no longer unscored: its transcribed page is the `scanned` stratum in
`reports/eval.md` (traditional WER 0.016, Docling 0.150), so that 0.12% backend deviation
now sits inside a scored row and should be kept in view when reading it.
