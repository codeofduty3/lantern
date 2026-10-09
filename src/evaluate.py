"""Part 9 - evaluate stage: WER/CER, numeric accuracy, cell P/R/F1, XBRL match rate, drift.

Ground truth (made from page images BEFORE looking at parser output):
  data/ground_truth/strata.csv            stem,page,stratum  (filings and fixtures)
  data/ground_truth/{stem}_p{N}.gt.txt    page transcriptions   (fixtures: tests/fixtures/gt/)
  data/ground_truth/{stem}_p{N}_t{K}.gt.csv  statement tables: [section,]label,<period...>
  python src/evaluate.py --render-gt      writes page images to transcribe from
Text normalization (both sides): lower-case, collapse whitespace, strip. Punctuation is KEPT
(removing it would hide sign errors such as (1,234)). Docling Markdown has table pipes, '#',
'*' and '<!-- -->' removed before scoring. Table cells compare unscaled printed values.

Output: reports/metrics.json, reports/eval.md, reports/docling_comparison.md,
        reports/format_decision.md (generated blocks), reports/drift/*.csv, reports/plots/drift.png
"""
import argparse
import json
import re
import sys
from pathlib import Path

import jiwer
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BENCH, DOCLING, EXPORT, FIXTURE_GT, FIXTURES, GROUND_TRUTH, PARSED, RENDERED,
                    REPORTS, TABLES, XBRL, load_manifest, numbers, write_report)
from tables import norm_label, to_number

NORM = jiwer.Compose([jiwer.ToLowerCase(), jiwer.RemoveMultipleSpaces(), jiwer.Strip(),
                      jiwer.ReduceToListOfListOfWords()])
NUM = re.compile(r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?")


# ------------------------------------------------------------------ text metrics (Lab 9)
def score_page(ref: str, hyp: str) -> dict:
    ref, hyp = " ".join(ref.split()), " ".join((hyp or "").split()) or "<empty>"
    out = jiwer.process_words(ref, hyp, reference_transform=NORM, hypothesis_transform=NORM)
    r_nums = [m.group() for m in NUM.finditer(ref)]
    h_nums = set(m.group() for m in NUM.finditer(hyp))
    hit = sum(n in h_nums for n in r_nums)
    return {"wer": out.wer, "sub": out.substitutions, "del": out.deletions,
            "ins": out.insertions, "cer": jiwer.cer(ref.lower(), hyp.lower()),
            "num_acc": hit / max(len(r_nums), 1)}


def strip_md(md: str) -> str:
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    md = re.sub(r"^\s*\|?\s*:?-{3,}.*$", " ", md, flags=re.M)  # table separator rows
    return re.sub(r"[|#*]", " ", md)


# ------------------------------------------------------------------ table metrics (Lab 9)
def cell_set(df: pd.DataFrame, use_section: bool, scale=1.0) -> set:
    """Tidy (section,label,period,raw) or GT wide (section?,label,<periods>) -> cell set."""
    cells = set()
    if {"period", "raw"} <= set(df.columns):
        for r in df.itertuples():
            v = to_number(str(r.raw), scale)
            if v is not None:
                key = (norm_label(r.section) if use_section else "", norm_label(r.label))
                cells.add(key + (str(r.period), round(v, 2)))
        return cells
    periods = [c for c in df.columns if c not in ("section", "label")]
    for _, row in df.iterrows():
        sec = norm_label(str(row.get("section", ""))) if use_section else ""
        for p in periods:
            v = to_number(str(row[p]), scale) if str(row[p]) != "nan" else None
            if v is not None:
                cells.add((sec, norm_label(str(row["label"])), str(p).strip(), round(v, 2)))
    return cells


def prf(pred: set, gold: set) -> dict:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    vr = len({c[-1] for c in pred} & {c[-1] for c in gold}) / max(len({c[-1] for c in gold}), 1)
    return {"precision": p, "recall": r, "f1": f, "value_recall": vr}


def pred_cells(path, stem, page):
    if path == "traditional":
        files = sorted(TABLES.glob(f"{stem}_p{page:04d}_t*.cells.csv"))
    else:
        idx = DOCLING / "tables_index.csv"
        ix = pd.read_csv(idx) if idx.exists() else pd.DataFrame(columns=["stem", "page", "table"])
        files = [DOCLING / f"{stem}_t{int(t):03d}.cells.csv"
                 for t in ix[(ix["stem"] == stem) & (ix["page"] == page)]["table"]]
    dfs = [pd.read_csv(f, dtype=str).fillna("") for f in files if f.exists()]
    return pd.concat(dfs) if dfs else pd.DataFrame(columns=["section", "label", "period", "raw"])


# ------------------------------------------------------------------ ground truth
def gt_dirs():
    return [GROUND_TRUTH, FIXTURE_GT]


def load_strata():
    f = GROUND_TRUTH / "strata.csv"
    return pd.read_csv(f) if f.exists() else pd.DataFrame(columns=["stem", "page", "stratum"])


def find_gt(name):
    for d in gt_dirs():
        if (d / name).exists():
            return d / name
    return None


def render_gt():
    """Page images to transcribe from (so ground truth never starts from parser output)."""
    out = GROUND_TRUTH / "images"
    out.mkdir(parents=True, exist_ok=True)
    for r in load_strata().itertuples():
        pdf = RENDERED / f"{r.stem}.pdf"
        pdf = pdf if pdf.exists() else FIXTURES / f"{r.stem}.pdf"
        with pdfplumber.open(pdf) as p:
            p.pages[int(r.page) - 1].to_image(resolution=150).save(
                out / f"{r.stem}_p{int(r.page)}.png")
    print(f"page images -> {out}")


# ------------------------------------------------------------------ drift
def drift_signals() -> pd.DataFrame:
    rows = []
    for f in sorted(EXPORT.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("text"):
                w = r["text"].split()
                rows.append({"stem": f.stem, "block_words": len(w),
                             "numeric_ratio": len(numbers(r["text"])) / max(len(w), 1)})
    return pd.DataFrame(rows)


def plot_drift(cur: pd.DataFrame):
    d = REPORTS / "drift"
    d.mkdir(parents=True, exist_ok=True)
    cur.to_csv(d / "current.csv", index=False)
    base = d / "baseline.csv"
    (REPORTS / "plots").mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    bins = [0, 10, 25, 50, 100, 150, 200, 300, 500, 2000]
    series = [("current", cur)] + ([("baseline", pd.read_csv(base))] if base.exists() else [])
    for name, df in series:
        ax[0].hist(df["block_words"], bins=bins, alpha=0.5, label=name)
        ax[1].hist(df["numeric_ratio"], bins=20, alpha=0.5, label=name)
    ax[0].set(title="Block length (words)", xscale="log")
    ax[1].set(title="Numeric-token ratio per block")
    for x in ax:
        x.legend()
    fig.tight_layout()
    fig.savefig(REPORTS / "plots" / "drift.png", dpi=120)
    return base.exists()


# ------------------------------------------------------------------ main
def fmt(v):
    return "-" if v is None else f"{v:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-gt", action="store_true", help="write GT page images and exit")
    ap.add_argument("--save-baseline", action="store_true",
                    help="store the current drift signals as the baseline version")
    a = ap.parse_args()
    if a.render_gt:
        return render_gt()
    manifest = load_manifest()
    strata = load_strata()

    # text: every GT page, both paths
    text_rows = []
    for r in strata.itertuples():
        gt = find_gt(f"{r.stem}_p{int(r.page)}.gt.txt")
        if gt is None:
            continue
        ref = gt.read_text(encoding="utf-8")
        for path, hyp_file in (("traditional", PARSED / f"{r.stem}_p{int(r.page):04d}.txt"),
                               ("docling", DOCLING / f"{r.stem}_p{int(r.page):04d}.md")):
            if not hyp_file.exists():
                continue
            hyp = hyp_file.read_text(encoding="utf-8")
            hyp = strip_md(hyp) if path == "docling" else hyp
            text_rows.append({"stem": r.stem, "page": int(r.page), "stratum": r.stratum,
                              "path": path, **score_page(ref, hyp)})
    text = pd.DataFrame(text_rows)

    # tables: every GT table, both paths
    tab_rows, pooled = [], {"traditional": [set(), set()], "docling": [set(), set()]}
    for d in gt_dirs():
        for g in sorted(d.glob("*_t*.gt.csv")):
            m = re.match(r"(.+)_p(\d+)_t(\d+)\.gt$", g.stem)
            stem, page = m.group(1), int(m.group(2))
            gdf = pd.read_csv(g, dtype=str).fillna("")
            use_sec = "section" in gdf.columns
            gold = cell_set(gdf, use_sec)
            for path in ("traditional", "docling"):
                if path == "docling" and not (DOCLING / "tables_index.csv").exists():
                    continue  # Docling stage not run yet: no row rather than a fake 0
                pred = cell_set(pred_cells(path, stem, page), use_sec)
                tab_rows.append({"table": g.name, "path": path, "gold": len(gold),
                                 "pred": len(pred), **prf(pred, gold)})
                pooled[path][0] |= {(g.name,) + c for c in pred}
                pooled[path][1] |= {(g.name,) + c for c in gold}
    tabs = pd.DataFrame(tab_rows)

    # xbrl, ocr share
    cmp_f = XBRL / "comparison.csv"
    cmp = pd.read_csv(cmp_f) if cmp_f.exists() else pd.DataFrame(columns=["path", "status"])
    cmp = cmp[cmp["status"] != "no_table"]
    log = pd.read_csv(PARSED / "ocr_log.csv")
    log_f = log[log["stem"].isin(manifest)] if manifest else log

    def text_mean(path, k):
        t = text[text["path"] == path] if len(text) else text
        return float(t[k].mean()) if len(t) else None

    metrics = {"text": {p: {k: text_mean(p, k) for k in ("wer", "cer", "num_acc")}
                        for p in ("traditional", "docling")},
               "tables": {p: ({k: prf(*pooled[p])[k] for k in
                               ("precision", "recall", "f1")}
                              if pooled[p][1] and (tabs["path"] == p).any()
                              else {"precision": None, "recall": None, "f1": None})
                          for p in ("traditional", "docling")},
               "xbrl": {p: {"match_rate": float((cmp[cmp["path"] == p]["status"] == "match")
                                                .mean()) if (cmp["path"] == p).any() else None}
                        for p in ("traditional", "docling")},
               "ocr": {"pages_ocr_share": float((log_f["engine"] != "pdfplumber").mean())}}
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # drift
    if a.save_baseline:
        cur = drift_signals()
        (REPORTS / "drift").mkdir(parents=True, exist_ok=True)
        cur.to_csv(REPORTS / "drift" / "baseline.csv", index=False)
    has_base = plot_drift(drift_signals())

    # reports
    md = ["Normalization: lower-case, collapse whitespace, strip; punctuation kept. Docling "
          "Markdown syntax removed before scoring. Table cells: unscaled printed values.\n",
          "## Text per page\n",
          text.round(4).to_markdown(index=False) if len(text) else "No ground-truth pages yet.",
          "\n## Text per stratum (mean)\n",
          text.groupby(["stratum", "path"])[["wer", "cer", "num_acc"]].mean().round(4)
          .reset_index().to_markdown(index=False) if len(text) else "-",
          "\n## Tables (cell precision / recall / F1)\n",
          tabs.round(4).to_markdown(index=False) if len(tabs) else "No ground-truth tables yet.",
          "\n## Corpus metrics (reports/metrics.json)\n", "```json", json.dumps(metrics, indent=2),
          "```", f"\nDrift plot: reports/plots/drift.png ({'baseline vs current' if has_base else 'current only - run with --save-baseline on the previous version'})."]
    write_report(REPORTS / "eval.md", "Evaluation", "\n".join(md),
                 "Paste `dvc metrics diff` output here, and the failing test run that proves "
                 "the regression tests have teeth.")

    bench = {}
    for f in BENCH.glob("*.csv"):
        b = pd.read_csv(f)
        if "status" in b.columns:
            b = b[~b["status"].astype(str).str.startswith("error:")]
        if len(b):
            # Model stages mark a cold first page; use the warm pages when they
            # exist, otherwise the whole sample (text/tables have no warm-up).
            warm = b[b["start"] == "warm"] if "start" in b.columns else b
            sample = warm if len(warm) else b
            bench[f.stem] = float(sample["seconds"].median())
    if "parse_docling" not in bench and (DOCLING / "timings.csv").exists():
        timings = pd.read_csv(DOCLING / "timings.csv")
        timings = timings[timings["stem"].isin(manifest)]
        if len(timings) and timings["pages"].sum():
            bench["parse_docling"] = float(timings["seconds"].sum() / timings["pages"].sum())

    def stratum_wer(path, pattern):
        if not len(text):
            return "not scored (no text GT)"
        subset = text[(text["path"] == path) &
                      text["stratum"].astype(str).str.contains(pattern, case=False, regex=True)]
        return fmt(float(subset["wer"].mean())) if len(subset) else "not scored (no matching GT stratum)"

    def bench_coverage(stage):
        path = BENCH / f"{stage}.csv"
        if not path.exists():
            return "not run"
        sample = pd.read_csv(path)
        status = sample["status"].astype(str)
        empty = int((status == "empty").sum())
        errors = int(status.str.startswith("error:").sum())
        return f"{len(sample)} pages; {len(sample) - empty - errors} non-empty; " \
               f"{empty} empty; {errors} errors"

    hv = DOCLING / "html_vs_pdf.csv"
    comp = ["| dimension | traditional | docling | source |", "|---|---|---|---|",
            f"| WER (mean) | {fmt(metrics['text']['traditional']['wer'])} | "
            f"{fmt(metrics['text']['docling']['wer'])} | eval.md |",
            f"| reading-order WER (multi-column stratum) | "
            f"{stratum_wer('traditional', 'multi.?col|reading.?order')} | "
            f"{stratum_wer('docling', 'multi.?col|reading.?order')} | eval.md; "
            "tests/fixtures/gt/CONVENTIONS.md |",
            f"| footnote-text WER | {stratum_wer('traditional', 'footnote')} | "
            f"{stratum_wer('docling', 'footnote')} | "
            "eval.md; requires footnote ground-truth stratum |",
            f"| CER (mean) | {fmt(metrics['text']['traditional']['cer'])} | "
            f"{fmt(metrics['text']['docling']['cer'])} | eval.md |",
            f"| numeric accuracy | {fmt(metrics['text']['traditional']['num_acc'])} | "
            f"{fmt(metrics['text']['docling']['num_acc'])} | eval.md |",
            f"| table cell F1 | {fmt(metrics['tables']['traditional']['f1'])} | "
            f"{fmt(metrics['tables']['docling']['f1'])} | eval.md |",
            f"| XBRL match rate | {fmt(metrics['xbrl']['traditional']['match_rate'])} | "
            f"{fmt(metrics['xbrl']['docling']['match_rate'])} | xbrl.md |",
            f"| s/page p50 | {fmt(bench.get('parse_pdfplumber'))} (text) / "
            f"{fmt(bench.get('tables'))} (tables) / {fmt(bench.get('layout'))} (layout) | "
            f"{fmt(bench.get('parse_docling'))} | benchmarks.md |",
            f"| Part 10 coverage | text: {bench_coverage('parse_pdfplumber')}; "
            f"tables: {bench_coverage('tables')}; layout: {bench_coverage('layout')} | "
            f"{bench_coverage('parse_docling')} | data/bench/*.csv |",
            "| provenance | page + bbox per block (layout) | page + bbox per item (prov.jsonl, "
            "normalized to top-left) | data/export, data/docling |"]
    if len(text):
        s = text.pivot_table(index="stratum", columns="path", values="wer").round(4)
        comp += ["", "WER by stratum (reading order shows on multi-column pages):\n",
                 s.reset_index().to_markdown(index=False)]
    if hv.exists():
        comp += ["", "Rendered PDF vs original iXBRL HTML (Docling), data/docling/html_vs_pdf.csv:\n",
                 pd.read_csv(hv).to_markdown(index=False)]
    write_report(REPORTS / "docling_comparison.md", "Docling vs traditional pipeline",
                 "\n".join(comp),
                 "Footnotes audit (5 notes pages), reading-order examples, and the one-paragraph "
                 "recommendation to Lina: primary path and fallback.")

    fs = EXPORT / "format_sizes.csv"
    if fs.exists():
        write_report(REPORTS / "format_decision.md", "Storage format decision",
                     pd.read_csv(fs).to_markdown(index=False) +
                     "\n\napprox_tokens = characters / 4.",
                     "Three retrieval questions asked of each format (LLM chat), answers and "
                     "correctness, then: source of truth, what feeds Case Study 2, and why.")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
