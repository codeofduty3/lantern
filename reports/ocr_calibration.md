# OCR Calibration on AKAM

## Data and method

Trigger signals were read from `data/parsed/ocr_log.csv`, generated from both rendered AKAM
filings and the scanned fixture. The scanned fixture contains AKAM 10-K pages 1, 13, and 53,
rasterized at 200 DPI with grayscale, skew, blur, and JPEG artifacts. Its PDF pages are known
scans by construction. For the DPI sweep, OCR output was scored against the text layer from the
corresponding original AKAM PDF pages. That is a useful proxy reference, not a hand-checked
transcription; no scanned-page text ground truth is currently present.

## Trigger signal observations

| Sample | Pages | Non-space chars | Junk ratio | Image coverage | OCR routed |
| --- | ---: | ---: | ---: | ---: | ---: |
| AKAM 10-K + 10-Q native PDFs | 160 | 1 to 5,662; 159 pages have at least 334 | max 0.0356 | 0.0 | 1 |
| AKAM-derived scanned fixture | 3 | 0 on all pages | 0.0 | 1.0 | 3 |

With `min_chars: 100`, the low-text 10-Q page 2 and all three scans route to OCR; the other 159
native filing pages stay on the text layer. Any integer cutoff from 2 through 334 makes the same
decision on this sample, so 100 is a conservative value within the observed gap, not a uniquely
optimized threshold.

For image coverage, any threshold strictly between 0 and 1 separates the observed native pages
from the scanned fixture. The configured 0.6 remains a reasonable midpoint, but the sample does
not establish it as uniquely optimal. The available pages do not include a labeled garbled
text-layer example. `junk_ratio: 0.2` is therefore retained as a provisional guard; it is above
the maximum observed ratio on the native AKAM pages, but has not been calibrated for detecting
garbling.

## DPI sweep

Each scanned fixture page was OCR'd at five resolutions. The reference pages were AKAM 10-K
pages 1, 13, and 53, respectively. Values below are means across those three pages; runtime is
wall-clock seconds per page in this local run.

| DPI | Mean WER | Mean CER | Mean numeric accuracy | Mean seconds/page |
| ---: | ---: | ---: | ---: | ---: |
| 150 | 0.0514 | 0.0093 | 0.9792 | 2.74 |
| 200 | 0.0206 | 0.0044 | 1.0000 | 3.25 |
| 250 | 0.0295 | 0.0063 | 1.0000 | 3.64 |
| 300 | 0.0321 | 0.0064 | 0.9896 | 4.04 |
| 400 | 0.0327 | 0.0062 | 0.9844 | 4.81 |

200 DPI had the lowest mean WER, perfect numeric accuracy on all three pages, and lower runtime
than 250 DPI and above. It is selected for now. This result is based on only three degraded
pages and a PDF text-layer proxy; confirm with hand-transcribed ground truth before treating it
as a general optimum.

## Managed fallback confidence

Four Textract `AnalyzeDocument(TABLES)` requests were made in `us-east-1` and cached under
`data/managed`. The comparison used the original AKAM PDF text layer as a proxy reference, not
hand-transcribed OCR ground truth.

| Sample | Tesseract confidence | Textract confidence | Tesseract WER | Textract WER |
| --- | ---: | ---: | ---: | ---: |
| 10-Q page 2 (blank except printed page number) | 92.0 | 0.0 | 0.0000 | 1.0000 |
| Scanned 10-K page 1 | 93.3 | 99.0 | 0.0420 | 0.0443 |
| Scanned 10-K page 13 | 95.4 | 99.8 | 0.0044 | 0.0000 |
| Scanned 10-K page 53 | 93.0 | 99.7 | 0.0155 | 0.0052 |

All tested Tesseract confidences at the configured 200 DPI exceed 70, so the current cutoff
would not invoke Textract on any of these pages. The blank 10-Q page is correctly read as its
page number by Tesseract; Textract returns no text for it. Across the three scans, Textract is
slightly worse on page 1 and better on pages 13 and 53, but these tiny samples and proxy scores
do not identify a defensible confidence boundary. Keep `managed_below_conf: 70` provisional.
To tune it, add hand-verified ground truth for genuinely low-confidence scans and compare both
engines on those same pages, grouped by Tesseract confidence. Managed API calls remain disabled
by default; the explicit calibration requests above were forced and their responses are cached.

Review the drafts in `reports/ocr_calibration_drafts/` against the images; only after correction
should they be promoted to ground truth and used for final OCR accuracy claims.
