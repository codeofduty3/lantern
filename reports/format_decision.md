# Storage format decision

<!-- AUTO:START (generated, do not edit) -->
| stem              | format   |   bytes |   chars |   approx_tokens |
|:------------------|:---------|--------:|--------:|----------------:|
| AKAM_10K_20241231 | jsonl    |  639059 |  638195 |          159548 |
| AKAM_10K_20241231 | md       |  385412 |  384786 |           96196 |
| AKAM_10K_20241231 | txt      |  269789 |  269163 |           67290 |
| AKAM_10Q_20250930 | jsonl    |  385534 |  385032 |           96258 |
| AKAM_10Q_20250930 | md       |  256881 |  256523 |           64130 |
| AKAM_10Q_20250930 | txt      |  168695 |  168337 |           42084 |

approx_tokens = characters / 4.
<!-- AUTO:END -->

## Discussion

### Size

Relative to plain text, Markdown costs about 1.4-1.5x the tokens (headings and the
`<!-- doc page block -->` provenance labels), and JSONL about 2.3-2.4x (every record repeats
the filing's identity, fiscal fields, source path and hash, plus its bbox and extractor). The
ratios are the same for the 10-K and the 10-Q, so they reflect the formats rather than one
document.

| Filing | TXT tokens | Markdown | JSONL |
|---|---|---|---|
| 10-K (FY2024) | 66,830 | 95,448 (1.43x TXT) | 157,942 (2.36x TXT) |
| 10-Q (Q3 2025) | 41,352 | 62,810 (1.52x TXT) | 95,808 (2.32x TXT) |

### LLM retrieval test

Setup: one document (AKAM 10-Q, quarter ended September 30, 2025), three questions, the same
LLM (ChatGPT, GPT-6 Luna) for every format, a new chat per format, file uploaded. The 10-Q was
used because the 10-K JSONL (about 158,000 tokens) is too large for a single chat.

Questions:

1. What was net income for the three months ended September 30, 2025, and on which page does it appear?
2. What was revenue for the nine months ended September 30, 2025, and on which page does it appear?
3. What was cash and cash equivalents as of September 30, 2025, and on which page does it appear?

Answer key, read from the rendered PDF (not from any pipeline output): net income $140,170
thousand and revenue $3,113,263 thousand on PDF page 6 (Condensed Consolidated Statements of
Income); cash and cash equivalents $927,933 thousand on PDF page 4 (Condensed Consolidated
Balance Sheets). Net income was checked by recomputing it from revenue, costs, other income
and taxes on the same page.

Marking rule, set before asking: correct = right value and right PDF page; partly correct =
right value, wrong or missing page; wrong = wrong value.

| Format | Values | Pages given (original question) | Pages given (clarified) | Result |
|---|---|---|---|---|
| TXT | 3/3 | 7, 7, 6 | "not determinable from this file" | 3 partly correct |
| Markdown | 3/3 | 5, 5, 3 | 6, 6, 4 | 3/3 correct |
| JSONL | 3/3 | (asked clarified) | 6, 6, 4 | 3/3 correct |

All three formats returned the correct values. Only the formats carrying provenance could give
the PDF page. With TXT, the model said it inferred pages from the filing's printed page
numbers, and when asked for PDF pages it said the file did not contain them. The original
question did not say which page numbering was meant: the Markdown run reported the filing's
printed pages (one behind the PDF, because the cover page is unnumbered) even though it read
the `p6` labels, and gave the correct PDF pages once the question was clarified with a
follow-up. The JSONL run was asked the clarified question from the start, and was noticeably
slower to answer.

### Decision

**Source of truth: JSONL.** It is the only format with every field on every record (including
the bbox, which the Markdown labels do not carry), validated against the schema on write, with
identical keys across documents. The Markdown and TXT exports can be regenerated from it.

**Feeds Case Study 2: Markdown.** It answered every question as accurately as JSONL, including
exact PDF pages, at 66% of JSONL's tokens (62,810 vs 95,808). Its provenance labels let a
retrieval system cite the page, and the block ID links back to the JSONL record for the bbox.

**TXT: baseline only.** It is the smallest (41,352 tokens) and got every value right, but
without provenance an answer cannot be traced to a page.

### Limitations

- The exports contain only the text captured by the layout stage, so absolute sizes understate
  the full filing; the ratios between formats are what the decision rests on.
- A small test: one document, three questions, one model.
- Questions about location must state which page numbering they mean (PDF page vs. printed
  page); the first round of answers showed how easily the two are confused.
