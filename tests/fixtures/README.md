# Test fixtures (committed to Git; CI inputs)

- `scanned.pdf`: pages [1, 13, 53] of `AKAM_10K_20241231.pdf` rasterized at 200 DPI with grayscale, skew, blur and JPEG artefacts, rebuilt as an image-only PDF (`src/make_fixtures.py`).
- `statement.pdf`: page 53 of `AKAM_10K_20241231.pdf` (income statement).
- `multicol.pdf`: SYNTHETIC: text of AKAM_10K_20241231.pdf page 13 re-rendered in two CSS columns (our filings have no multi-column page). Replace via params fixtures.multicol_pdf.
- `gt/`: hand transcriptions (`<fixture>_p<N>.gt.txt`) and the statement table (`statement_p1_t1.gt.csv`); conventions in `gt/CONVENTIONS.md`.
