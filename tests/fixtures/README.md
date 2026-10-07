# Test fixtures (committed to Git; CI inputs)

- `scanned.pdf`: pages [1, 13, 53] of `AKAM_10K_20241231.pdf` rasterized at 200 DPI with grayscale, skew, blur and JPEG artefacts, rebuilt as an image-only PDF (`src/make_fixtures.py`).
- `statement.pdf`: page 53 of `AKAM_10K_20241231.pdf` (income statement).
- `multicol.pdf`: page 103 ("Our Leadership", two columns under a full-width title) of Akamai Technologies Form ARS for FY2024, a public SEC filing (accession 0001193125-25-070456): https://www.sec.gov/Archives/edgar/data/1086222/000119312525070456/d846830dars.pdf. Our 10-K and 10-Q have no multi-column page.
- `gt/`: hand transcriptions (`<fixture>_p<N>.gt.txt`) and the statement table (`statement_p1_t1.gt.csv`); conventions in `gt/CONVENTIONS.md`.