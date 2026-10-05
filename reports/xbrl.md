# XBRL validation

<!-- AUTO:START (generated, do not edit) -->
## Match rate per statement and extraction path

| filing | statement | path | lines x periods | match | match rate |
|---|---|---|---|---|---|
| AKAM_10K_20241231 | balance_sheet | docling | 68 | 67 | 98.5% |
| AKAM_10K_20241231 | balance_sheet | traditional | 68 | 65 | 95.6% |
| AKAM_10K_20241231 | income_statement | docling | 60 | 51 | 85.0% |
| AKAM_10K_20241231 | income_statement | traditional | 60 | 51 | 85.0% |
| AKAM_10Q_20250930 | balance_sheet | docling | 26 | 26 | 100.0% |
| AKAM_10Q_20250930 | balance_sheet | traditional | 43 | 36 | 83.7% |
| AKAM_10Q_20250930 | income_statement | docling | 76 | 68 | 89.5% |
| AKAM_10Q_20250930 | income_statement | traditional | 76 | 68 | 89.5% |

## Mapping methods

| path        | method   |   cells |
|:------------|:---------|--------:|
| docling     | label    |      12 |
| docling     | manual   |     218 |
| traditional | fuzzy    |       2 |
| traditional | label    |       8 |
| traditional | manual   |     190 |
| traditional | nospace  |      24 |
| traditional | suffix   |      19 |
| traditional | unmapped |       4 |

## Every non-match (suggested cause; confirm and add the fix below)

| stem              | path        | statement        | label                                                                                                    |   period | raw         |       pdf_value | concept                        |    xbrl_value | status       | method   | suggested_cause                                                       |
|:------------------|:------------|:-----------------|:---------------------------------------------------------------------------------------------------------|---------:|:------------|----------------:|:-------------------------------|--------------:|:-------------|:---------|:----------------------------------------------------------------------|
| AKAM_10K_20241231 | traditional | income_statement | interest expense                                                                                         |     2024 | (27,117)    |    -2.7117e+07  | InterestExpenseNonoperating    |   2.7117e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | interest expense                                                                                         |     2023 | (17,709)    |    -1.7709e+07  | InterestExpenseNonoperating    |   1.7709e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | interest expense                                                                                         |     2022 | (11,096)    |    -1.1096e+07  | InterestExpenseNonoperating    |   1.1096e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | other expense, net                                                                                       |     2024 | (19,561)    |    -1.9561e+07  | OtherNonoperatingExpenseNet    |   1.9561e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | other expense, net                                                                                       |     2023 | (12,296)    |    -1.2296e+07  | OtherNonoperatingExpenseNet    |   1.2296e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | other expense, net                                                                                       |     2022 | (10,433)    |    -1.0433e+07  | OtherNonoperatingExpenseNet    |   1.0433e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | provision for income taxes                                                                               |     2024 | (82,095)    |    -8.2095e+07  | IncomeTaxExpenseBenefit        |   8.2095e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | provision for income taxes                                                                               |     2023 | (106,373)   |    -1.06373e+08 | IncomeTaxExpenseBenefit        |   1.06373e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | income_statement | provision for income taxes                                                                               |     2022 | (126,696)   |    -1.26696e+08 | IncomeTaxExpenseBenefit        |   1.26696e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | traditional | balance_sheet    | at december 31, 2023                                                                                     |     2024 | 1,556       |     1.556e+06   |                                | nan           | xbrl_missing | unmapped | mapping: extension, dimensional or unmapped concept                   |
| AKAM_10K_20241231 | traditional | balance_sheet    | at december 31, 2023                                                                                     |     2023 | 1,512       |     1.512e+06   |                                | nan           | xbrl_missing | unmapped | mapping: extension, dimensional or unmapped concept                   |
| AKAM_10K_20241231 | traditional | balance_sheet    | treasury stock, at cost, 5,622,892 shares at december 31, 2024, and no shares at december 31, 2023       |     2024 | (558,488)   |    -5.58488e+08 | TreasuryStockCommonValue       |   5.58488e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | interest expense                                                                                         |     2024 | (27,117)    |    -2.7117e+07  | InterestExpenseNonoperating    |   2.7117e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | interest expense                                                                                         |     2023 | (17,709)    |    -1.7709e+07  | InterestExpenseNonoperating    |   1.7709e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | interest expense                                                                                         |     2022 | (11,096)    |    -1.1096e+07  | InterestExpenseNonoperating    |   1.1096e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | other expense, net                                                                                       |     2024 | (19,561)    |    -1.9561e+07  | OtherNonoperatingExpenseNet    |   1.9561e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | other expense, net                                                                                       |     2023 | (12,296)    |    -1.2296e+07  | OtherNonoperatingExpenseNet    |   1.2296e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | other expense, net                                                                                       |     2022 | (10,433)    |    -1.0433e+07  | OtherNonoperatingExpenseNet    |   1.0433e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | provision for income taxes                                                                               |     2024 | (82,095)    |    -8.2095e+07  | IncomeTaxExpenseBenefit        |   8.2095e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | provision for income taxes                                                                               |     2023 | (106,373)   |    -1.06373e+08 | IncomeTaxExpenseBenefit        |   1.06373e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | income_statement | provision for income taxes                                                                               |     2022 | (126,696)   |    -1.26696e+08 | IncomeTaxExpenseBenefit        |   1.26696e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10K_20241231 | docling     | balance_sheet    | treasury stock, at cost, 5,622,892 shares at december 31, 2024, and no shares at december 31, 2023       |     2024 | (558,488)   |    -5.58488e+08 | TreasuryStockCommonValue       |   5.58488e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | interest expense                                                                                         |     2025 | (7,915)     |    -7.915e+06   | InterestExpenseNonoperating    |   7.915e+06   | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | interest expense                                                                                         |     2024 | (6,735)     |    -6.735e+06   | InterestExpenseNonoperating    |   6.735e+06   | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | interest expense                                                                                         |   2025_2 | (22,866)    |    -2.2866e+07  | InterestExpenseNonoperating    |   2.2866e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | interest expense                                                                                         |   2024_2 | (20,382)    |    -2.0382e+07  | InterestExpenseNonoperating    |   2.0382e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | provision for income taxes                                                                               |     2025 | (32,995)    |    -3.2995e+07  | IncomeTaxExpenseBenefit        |   3.2995e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | provision for income taxes                                                                               |     2024 | (15,899)    |    -1.5899e+07  | IncomeTaxExpenseBenefit        |   1.5899e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | provision for income taxes                                                                               |   2025_2 | (131,527)   |    -1.31527e+08 | IncomeTaxExpenseBenefit        |   1.31527e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | income_statement | provision for income taxes                                                                               |   2024_2 | (63,891)    |    -6.3891e+07  | IncomeTaxExpenseBenefit        |   6.3891e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | balance_sheet    | rating leas e liabi lities                                                                               |     2025 | 846,619     |     8.46619e+08 | OperatingLeaseLiabilityCurrent |   2.81347e+08 | mismatch     | suffix   | period alignment / column shift, or wrong concept (check mapping)     |
| AKAM_10Q_20250930 | traditional | balance_sheet    | rating leas e liabi lities                                                                               |     2024 | 829,660     |     8.2966e+08  | OperatingLeaseLiabilityCurrent |   2.59134e+08 | mismatch     | suffix   | period alignment / column shift, or wrong concept (check mapping)     |
| AKAM_10Q_20250930 | traditional | balance_sheet    | common stock, $0.01 par value ; 700,000,00 0 shares aut horized; 159,113,000 shares issued and           |     2025 | 143,767,4   |     1.43767e+09 | CommonStockValue               |   1.591e+06   | mismatch     | manual   | period alignment / column shift, or wrong concept (check mapping)     |
| AKAM_10Q_20250930 | traditional | balance_sheet    | outstandin g at d ecember 31, 20                                                                         |     2025 | 24          | 24000           |                                | nan           | xbrl_missing | unmapped | mapping: extension, dimensional or unmapped concept                   |
| AKAM_10Q_20250930 | traditional | balance_sheet    | outstandin g at d ecember 31, 20                                                                         |     2024 | 1,556       |     1.556e+06   |                                | nan           | xbrl_missing | unmapped | mapping: extension, dimensional or unmapped concept                   |
| AKAM_10Q_20250930 | traditional | balance_sheet    | treasury s tock, at cost, 15,345,5 37 shares at september 30, 2025, and 5,622,892 shares at december 31, |     2025 | (1,335,236) |    -1.33524e+09 | TreasuryStockCommonValue       |   1.33524e+09 | sign         | fuzzy    | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | traditional | balance_sheet    | treasury s tock, at cost, 15,345,5 37 shares at september 30, 2025, and 5,622,892 shares at december 31, |     2024 | (558,488    |    -5.58488e+08 | TreasuryStockCommonValue       |   5.58488e+08 | sign         | fuzzy    | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | interest expense                                                                                         |     2025 | (7,915)     |    -7.915e+06   | InterestExpenseNonoperating    |   7.915e+06   | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | interest expense                                                                                         |     2024 | (6,735)     |    -6.735e+06   | InterestExpenseNonoperating    |   6.735e+06   | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | interest expense                                                                                         |   2025_2 | (22,866)    |    -2.2866e+07  | InterestExpenseNonoperating    |   2.2866e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | interest expense                                                                                         |   2024_2 | (20,382)    |    -2.0382e+07  | InterestExpenseNonoperating    |   2.0382e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | provision for income taxes                                                                               |     2025 | (32,995)    |    -3.2995e+07  | IncomeTaxExpenseBenefit        |   3.2995e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | provision for income taxes                                                                               |     2024 | (15,899)    |    -1.5899e+07  | IncomeTaxExpenseBenefit        |   1.5899e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | provision for income taxes                                                                               |   2025_2 | (131,527)   |    -1.31527e+08 | IncomeTaxExpenseBenefit        |   1.31527e+08 | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
| AKAM_10Q_20250930 | docling     | income_statement | provision for income taxes                                                                               |   2024_2 | (63,891)    |    -6.3891e+07  | IncomeTaxExpenseBenefit        |   6.3891e+07  | sign         | manual   | presentation: statement shows the value negated vs XBRL (sign policy) |
<!-- AUTO:END -->

## Discussion

### 1. Results

Overall match rate per extraction path, at each stage of the work (share of extracted
line-period cells whose normalized value equals the filing's own XBRL fact):

| stage | traditional | Docling |
|---|---|---|
| original (standard-label mapping only) | 70.0% | 87.0% |
| + mapping through all of the filing's label roles | 81.4% | 92.2% |
| + candidates restricted by statement type (instant/duration) | 81.4% (unchanged) | 92.2% (unchanged) |
| + extraction-tolerant matching (this run) | **89.1%** | **92.2%** |

Counting the sign-convention rows (same magnitude, opposite sign — see policy below) as
correctly extracted, the final rates are **traditional 97.2%** and **Docling 100.0%**.

Per filing and statement after this run (strict rate, then the rate counting sign rows
as correct):

| filing | statement | traditional | Docling |
|---|---|---|---|
| 10-K 2024 | balance sheet | 95.6% / 97.1% | 98.5% / 100.0% |
| 10-K 2024 | income statement | 85.0% / 100.0% | 85.0% / 100.0% |
| 10-Q Sep 2025 | balance sheet | 83.7% / 88.4% | 100.0% / 100.0% |
| 10-Q Sep 2025 | income statement | 89.5% / 100.0% | 89.5% / 100.0% |

### 2. Fixes made

**a. The 10-Q tags some lines with different concepts than the 10-K.** Three statement
lines are tagged with different concepts in the two filings (found by searching
facts.csv for the printed values). The curated dictionary alone therefore mismapped the
10-Q. Fix: a curated concept is used only if the filing actually reports a fact for it;
otherwise the mapping falls through to the filing's own label linkbase, using every
label role (terse, total, negated, period start/end), not just the standard label.
Effect: overall traditional 70.0% → 81.4%, Docling 87.0% → 92.2%.

**b. A balance sheet row was fuzzy-matched to a cash flow concept.** The damaged 10-Q
label "other curr ent lia bilities" fuzzy-matched IncreaseDecreaseInOtherCurrentLiabilities,
a duration (cash flow) concept that can never be right on a balance sheet. Fix:
candidates are restricted by statement type — balance sheet rows can only map to
concepts the filing reports as instants, income statement rows only to durations.
Match rates were unchanged; the two affected cells moved from a misleading
"xbrl_missing" to an honest "mismatch", which the next fix then resolved.

**c. Extraction-tolerant matching (four changes, this run).** The traditional table
path damages row labels; the validation now tolerates the common damage patterns
without touching the extracted tables themselves:
- *Space-insensitive matching* (method "nospace"): unmatched labels are retried against
  the curated dictionary and the filing's labels with all whitespace removed, so split
  words like "other curr ent lia bilities" or "deferred r evenu e" resolve normally.
- *Suffix matching for wrapped labels* (method "suffix"): a still-unmatched label is
  accepted if it is the whitespace-removed ending of exactly one caption of the right
  statement type. "below)" and "intangible assets shown below)" are the surviving last
  line of the wrapped caption "Cost of revenue (exclusive of amortization of acquired
  intangible assets shown below)" and now map to CostOfRevenue. The exactly-one rule
  refuses "at december 31, 2023", which ends two captions (common stock and treasury
  stock), rather than guessing.
- *Inferred balance sheet sections*: the 10-Q traditional balance sheet lost its
  section headings, so current and non-current lines with the same caption were mixed
  up (operating lease liabilities 281,347 vs 846,619 swapped; current deferred revenue
  and the current portion of the convertible notes mapped to the non-current concepts).
  When a row's extracted section is blank or not one the dictionary uses, it is now
  inferred from the row's position relative to the subtotal rows (total current assets,
  total assets, total current liabilities, total liabilities, matched with whitespace
  removed; rows were verified to be in table order). comparison.csv records
  section_source = extracted or inferred per row.
- *Clipped closing parenthesis*: a raw value that starts with "(" but has no ")" and
  parsed positive is treated as negative. "(155,993" (accumulated other comprehensive
  loss, 10-Q, Dec 31 2024 column) now matches its XBRL fact of −155,993.

Effect of (c): 20 cells that did not match before now match, and overall traditional
went 81.4% → 89.1% (10-Q balance sheet 55.8% → 83.7%, 10-K income statement
80.0% → 85.0%, 10-Q income statement 84.2% → 89.5%). Docling rates were untouched.
One cell moved the other way, from match to sign, for the right reason: the 10-Q
treasury stock Dec 31 2024 value, extracted as "(558,488" and parsed positive, had
coincidentally equalled the positive XBRL amount; with the clipped parenthesis repaired
it is negative and is now classified "sign", consistent with its own 2025 column and
with the same line in the 10-K.

### 3. Policies: scale and sign conventions

- **Scale**: every table value is normalized by the caption scale (amounts in
  thousands) before comparison, so PDF values and XBRL facts are compared in dollars.
- **Sign convention**: AKAM's statements print expenses (interest expense; other
  expense, net), the provision for income taxes, and treasury stock in parentheses,
  and the pipeline normalizes parenthesized values as negatives. Their XBRL concepts
  (InterestExpenseNonoperating, OtherNonoperatingExpenseNet, IncomeTaxExpenseBenefit,
  TreasuryStockCommonValue) store positive amounts by convention. Equal magnitude with
  opposite sign is classified "sign": the value was extracted correctly, and these rows
  are reported separately from matches (the second rate in the tables above).
- **Dash rows**: a dash means nil and is normalized to 0. AKAM tags the junior
  participating preferred stock line (no shares issued) with an explicit 0-value
  PreferredStockValue fact, so these rows compare as matches against 0.

### 4. Every remaining non-match

Values are as printed, in thousands of dollars; periods are collapsed per line.
Each cause was confirmed by checking the line against the rendered PDF pages (10-K pages
52–53, 10-Q pages 4–6), with the assignment's cause type and the fix made or the
pipeline stage where the open fix belongs.

| Path | PDF label | Concept | PDF value | XBRL value | Status | Mapping | Diagnosed cause / fix |
|---|---|---|---|---|---|---|---|
| both | interest expense (10-K: 2022–2024; 10-Q: 4 periods) | InterestExpenseNonoperating | −27,117 … −6,735 | same, positive | sign | manual | sign convention — normalization policy; correctly extracted, reported in the sign-inclusive rate; no fix needed |
| both | other expense, net (10-K 2022–2024) | OtherNonoperatingExpenseNet | −19,561 / −12,296 / −10,433 | same, positive | sign | manual | sign convention — as above |
| both | provision for income taxes (10-K: 3; 10-Q: 4 periods) | IncomeTaxExpenseBenefit | −82,095 … −15,899 | same, positive | sign | manual | sign convention — as above |
| both | treasury stock, at cost… (10-K 2024) | TreasuryStockCommonValue | −558,488 | 558,488 | sign | manual | sign convention — as above |
| traditional | at december 31, 2023 (10-K, 2 periods) | — | 1,556 / 1,512 | — | xbrl_missing | unmapped | wrapped label (table structure): last line of the wrapped common stock caption; the suffix rule correctly refuses it because two captions end this way; fix: join wrapped labels in the tables stage (Part 2) |
| traditional | rating leas e liabi lities (10-Q, 2 periods) | OperatingLeaseLiabilityCurrent | 846,619 / 829,660 | 281,347 / 259,134 | mismatch | suffix | table structure + mapping: first letters clipped, and the filing uses the same caption, "Operating lease liabilities", for both the current and non-current lines, so the clipped label maps to the current concept. root cause in the tables stage (Part 2); documented limitation. |
| traditional | common stock, $0.01 par value… (10-Q 2025) | CommonStockValue | 1,437,674 | 1,591 | mismatch | manual | wrapped label (table structure): the wrapped caption corrupted the value cell; fix: tables stage (Part 2) |
| traditional | outstandin g at d ecember 31, 20 (10-Q, 2 periods) | — | 24 / 1,556 | — | xbrl_missing | unmapped | wrapped label (table structure): continuation line of the common stock caption; fix: tables stage (Part 2) |
| traditional | treasury s tock, at cost… (10-Q 2025) | TreasuryStockCommonValue | −1,335,236 | 1,335,236 | sign | fuzzy | sign convention — as above |
| traditional | treasury s tock, at cost… (10-Q 2024) | TreasuryStockCommonValue | −558,488 | 558,488 | sign | fuzzy | sign convention (normalization): shown in parentheses, stored positive in XBRL. Raw "(558,488" had a clipped ")"; it matched only by accident before the parenthesis fix and now shows the same convention as the 2025 column and the 10-K. Policy, not an error. |

Every remaining non-match has a diagnosed cause.

Categories not observed on this corpus. OCR: both filings' statement pages have a text
layer, and no statement page needed OCR. Period alignment: once a line was mapped, every
value matched its period; this cause did occur on our earlier Apple run, where a header row
shifted the 10-Q columns. Rounding: every difference was either zero or far beyond the
tolerance derived from decimals. Extension concepts: all 45 remaining non-matches map to
standard us-gaap concepts (InterestExpenseNonoperating, IncomeTaxExpenseBenefit,
OtherNonoperatingExpenseNet, TreasuryStockCommonValue, OperatingLeaseLiabilityCurrent,
CommonStockValue) or to no concept; no company-specific akam: concept is involved.

### 5. Upstream causes in the tables stage (Part 2)

- The 10-Q balance sheet spans PDF pages 4–5; only page 5 was labeled balance_sheet on
  the traditional path, so the assets (page 4) were never extracted and are not in the
  match-rate denominator. (The Docling table for the same statement covers only the
  assets page, so the two paths' 10-Q balance sheet denominators are different pages.)
- On page 5, pdfplumber won the hybrid selection narrowly (0.77 vs 0.75 for
  stream/network), split words inside captions, and lost the section headings.
- Wrapped labels are not joined (the Cost of revenue caption, the common stock line).
- A closing parenthesis was clipped ("(155,993", "(558,488").

The validation now tolerates several of these (split words, wrapped captions, lost
sections, clipped parentheses), but the extracted tables themselves are unchanged and
the root causes remain in the tables stage.

### 6. Limitations

- The match rate only counts lines that were extracted: the 10-Q assets page is missing
  from the traditional path entirely, and the Docling 10-Q table covers only that page.
- Damaged labels can still match the wrong concept. Suffix matching fixed
  "r liabilitie s" (now OtherLiabilitiesNoncurrent, matching), but
  "rating leas e liabi lities" still lands on the current-portion concept because its
  surviving tail is the ending of that caption.
- Arelle warned about an older inline XBRL transformation namespace
  (http://www.sec.gov/inlineXBRL/transformation/2015-08-31) on duration and count
  facts; no statement line was affected.
