# Evaluation

<!-- AUTO:START (generated, do not edit) -->
Normalization: lower-case, collapse whitespace, strip; punctuation kept. Docling Markdown syntax removed before scoring. Table cells: unscaled printed values.

## Text per page

No ground-truth pages yet.

## Text per stratum (mean)

-

## Tables (cell precision / recall / F1)

| table                  | path        |   gold |   pred |   precision |   recall |   f1 |   value_recall |
|:-----------------------|:------------|-------:|-------:|------------:|---------:|-----:|---------------:|
| statement_p1_t1.gt.csv | traditional |     60 |     60 |        0.95 |     0.95 | 0.95 |              1 |
| statement_p1_t1.gt.csv | docling     |     60 |     60 |        1    |     1    | 1    |              1 |

## Corpus metrics (reports/metrics.json)

```json
{
  "text": {
    "traditional": {
      "wer": null,
      "cer": null,
      "num_acc": null
    },
    "docling": {
      "wer": null,
      "cer": null,
      "num_acc": null
    }
  },
  "tables": {
    "traditional": {
      "precision": 0.95,
      "recall": 0.95,
      "f1": 0.9500000000000001,
      "value_recall": 1.0
    },
    "docling": {
      "precision": 1.0,
      "recall": 1.0,
      "f1": 1.0,
      "value_recall": 1.0
    }
  },
  "xbrl": {
    "traditional": {
      "match_rate": 0.8906882591093117
    },
    "docling": {
      "match_rate": 0.9217391304347826
    }
  },
  "ocr": {
    "pages_ocr_share": 0.00625
  }
}
```

Drift plot: reports/plots/drift.png (current only - run with --save-baseline on the previous version).
<!-- AUTO:END -->

## Discussion

Paste `dvc metrics diff` output here, and the failing test run that proves the regression tests have teeth.
