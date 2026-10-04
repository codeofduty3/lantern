# Ground-truth conventions (tests/fixtures/gt and data/ground_truth)

Transcribe from the page IMAGE (`python src/evaluate.py --render-gt`), never from parser output.
Two people key statement tables independently and reconcile differences.

Text (`<stem>_p<N>.gt.txt`)
- Reading order: top to bottom; for multiple columns, finish the left column first.
- One line per printed line; blank line between paragraphs. Headers and footers included.
- Keep punctuation, `$`, `%`, parentheses and footnote markers exactly as printed.
- Dashes as printed (— for em dash). Curly quotes may be typed straight.
- Tables on a text page: one printed row per line, cells separated by single spaces.

Tables (`<stem>_p<N>_t<K>.gt.csv`)
- Columns: `section,label,<period>...` with periods as the header year (`2025,2024,2023`;
  10-Q year-to-date columns `2025_2,2024_2`).
- `section` = the heading row above the line without its colon (e.g. `Net sales`), empty
  after a Total line; `label` as printed without footnote markers.
- Values exactly as printed, unscaled: `416,161`, `(321)`, `—`, `6.08`. Omit `$`.
- Heading-only rows (no numbers) are not rows.

Statement tables (AKAM 10-K income statement and balance sheet)
- Taken from the filing's original iXBRL HTML (the document the PDF was rendered
  from), not from any pipeline output (data/tables, data/docling, data/parsed,
  data/export, data/layout) and not extracted from the rendered PDF with code.
- Values as printed in the HTML (commas, parentheses, em dash; no `$`), unscaled.
- Then verified line by line against the rendered PDF pages.
