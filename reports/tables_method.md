# Table extraction: bake-off and method choice

<!-- AUTO:START (generated, do not edit) -->
Camelot 2.0.0, pdfplumber 0.11.10. Same normalizer for every method. coverage = share of the page's printed numbers found in the table; placed = numbers assigned to a (label, period); merged = cells holding 2+ numbers.

## Bake-off

### AKAM_10K_20241231 page 53 (income_statement)

Printed numbers on page (excl. years/footer): 60; caption scale 1000.

| method | tables | shape | accuracy | whitespace | coverage | placed cells | merged | periods | sec | hand check (10) |
|---|---|---|---|---|---|---|---|---|---|---|
| lattice | 4 | 15x3 | 100.0 | 0.0 | 73% | 0 | 0 | 0 | 0.3 | not filled |
| stream | 1 | 27x7 | 98.99 | 46.03 | 100% | 60 | 0 | 3 | 0.0 | not filled |
| network | 1 | 22x6 | 98.93 | 42.42 | 100% | 3 | 0 | 3 | 0.0 | not filled |
| hybrid | 4 | 15x3 | 100.0 | 0.0 | 73% | 0 | 0 | 0 | 0.2 | not filled |
| pdfplumber | 1 | 36x9 | - | 62.04 | 92% | 0 | 0 | 0 | 0.0 | not filled |

Hand check pending: fill `reports/handcheck/AKAM_10K_20241231_p0053.csv` and rerun.

### AKAM_10K_20241231 page 52 (balance_sheet)

Printed numbers on page (excl. years/footer): 83; caption scale 1000.

| method | tables | shape | accuracy | whitespace | coverage | placed cells | merged | periods | sec | hand check (10) |
|---|---|---|---|---|---|---|---|---|---|---|
| lattice | 3 | 13x2 | 100.0 | 15.38 | 35% | 0 | 1 | 0 | 0.2 | not filled |
| stream | 1 | 46x3 | 100.0 | 15.94 | 100% | 68 | 0 | 2 | 0.0 | not filled |
| network | 2 | 28x5 | 97.7 | 47.14 | 63% | 0 | 0 | 0 | 0.1 | not filled |
| hybrid | 3 | 11x2 | 100.0 | 15.38 | 35% | 0 | 1 | 0 | 0.2 | not filled |
| pdfplumber | 1 | 68x10 | - | 70.88 | 98% | 68 | 1 | 2 | 0.0 | not filled |

Hand check pending: fill `reports/handcheck/AKAM_10K_20241231_p0052.csv` and rerun.

## Hand-check accuracy by table type

| table type | lattice | stream | network | hybrid | pdfplumber |
|---|---|---|---|---|---|
| income_statement | pending | pending | pending | pending | pending |
| balance_sheet | pending | pending | pending | pending | pending |

## Hybrid extractor: winning method per table (data/tables/tables_log.csv)

| table type | winning method | tables |
|---|---|---|
| balance_sheet | pdfplumber | 1 |
| balance_sheet | stream | 1 |
| cash_flows | network | 1 |
| cash_flows | stream | 3 |
| equity | lattice | 2 |
| equity | network | 1 |
| income_statement | stream | 3 |
| other table | lattice | 4 |
| other table | network | 22 |
| other table | pdfplumber | 10 |
| other table | stream | 49 |
<!-- AUTO:END -->

## Discussion

Write 3-5 sentences: preferred method per table type, citing the hand-check scores, coverage and merged-cell counts above, and one table where the winner loses and why.
