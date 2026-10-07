"""Part 11 - xbrl stage: Arelle facts, label->concept mapping, validation of both table paths.

1. Load each filing's unpacked iXBRL .htm (next to its .xsd) with Arelle; keep numeric facts with
   concept, value, period (instant/duration, end date minus one day), unit, decimals, dimensions;
   de-duplicate on (concept, period, dims, unit).
2. Map PDF row labels to concepts: config/label_map.yaml (curated) -> the filing's own label
   linkbase -> difflib fuzzy match. The method is recorded per line.
3. Compare every period with a tolerance from decimals; status in match, sign, scale_x...,
   mismatch, pdf_missing, xbrl_missing. Traditional = data/tables, Docling = data/docling.
4. Each non-match gets a suggested cause from the Lab 11 triage table; the team confirms it
   and records the fix in reports/xbrl.md.

Output: data/xbrl/facts.csv, data/xbrl/comparison.csv, reports/xbrl.md (generated block)
"""
import difflib
import re
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG, DOCLING, RAW, REPORTS, TABLES, XBRL, load_manifest
from tables import norm_label

STATEMENTS = ("income_statement", "balance_sheet")
PATHS = {"traditional": TABLES, "docling": DOCLING}


# ------------------------------------------------------------------ 1. facts
def ixbrl_file(accession: str) -> Path:
    for htm in (RAW / "sec-edgar-filings").rglob(f"{accession}/unpacked/*.htm"):
        if "ix:header" in htm.read_text(errors="ignore"):
            return htm
    raise FileNotFoundError(accession)


def load_facts(htm: Path, stem: str) -> tuple:  # (facts df, norm label -> concept)
    from arelle import Cntlr
    cntlr = Cntlr.Cntlr(logFileName="logToPrint")
    mx = cntlr.modelManager.load(str(htm))
    rows = []
    for f in mx.facts:
        if not f.isNumeric or f.xValue is None or f.context is None:
            continue
        c = f.context
        end = c.endDatetime - timedelta(days=1) if c.endDatetime else None  # Arelle gotcha
        start = c.startDatetime if not c.isInstantPeriod else None
        dims = ";".join(sorted(f"{d.localName}={v.memberQname.localName}"
                               for d, v in c.qnameDims.items() if v.memberQname is not None))
        rows.append({"stem": stem, "concept": f.concept.qname.localName,
                     "prefix": f.concept.qname.prefix, "label": f.concept.label(lang="en"),
                     "value": float(f.xValue), "instant": c.isInstantPeriod,
                     "start": start.date() if start else None, "end": end.date() if end else None,
                     "days": (end - start).days + 1 if start and end else 0,
                     "dims": dims, "unit": f.unitID, "decimals": f.decimals})
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(["concept", "instant", "start", "end", "dims", "unit"])
    lab2con = filing_labels(mx, set(df["concept"])) if len(df) else {}
    mx.close()
    return df, lab2con


def filing_labels(mx, reported: set) -> dict:
    """norm_label -> concept, from EVERY role in the filing's label linkbase.

    Statements print the preferred label of each line (terse/total/negated/periodStart...),
    so matching only the standard label misses most captions. Documentation labels are
    definitions, not captions, and are skipped. First mapping wins on collisions."""
    from arelle import XbrlConst
    out = {}
    for rel in mx.relationshipSet(XbrlConst.conceptLabel).modelRelationships:
        concept, res = rel.fromModelObject.qname.localName, rel.toModelObject
        if concept not in reported or res.role == XbrlConst.documentationLabel \
                or not res.textValue:
            continue
        out.setdefault(norm_label(res.textValue), concept)
    return out


# ------------------------------------------------------------------ 2. mapping
def load_map():
    return yaml.safe_load((CONFIG / "label_map.yaml").read_text()) or {}


def parse_target(t: str):
    """'Concept' or 'Concept[MemberLocalName]' -> (concept, member or None)."""
    m = re.fullmatch(r"([^\[]+)(?:\[([^\]]+)\])?", t.strip())
    return m.group(1), m.group(2)


NOSPACE = re.compile(r"\s+")


def nospace(s) -> str:
    """Key with every whitespace removed: tolerate split words ("other curr ent lia bilities")."""
    return NOSPACE.sub("", s or "")


def map_label(kind, section, label, curated, lab2con):
    """Candidates in cascade order: curated, the filing's own labels, fuzzy. The caller keeps
    the first one the filing tagged: companies tag the same line with different concepts in
    the 10-K and the 10-Q, so a curated concept with no fact must fall through."""
    key = f"{section} > {label}" if section else label
    cm = curated.get(kind, {}) or {}
    cands = []
    for k in (key, label):
        if k in cm:
            cands.append((cm[k], "manual"))
            break
    else:
        for k in sorted(cm, key=len, reverse=True):  # long labels: curated key is a prefix
            if " > " not in k and len(k) > 12 and label.startswith(k):
                cands.append((cm[k], "manual"))
                break
    if label in lab2con:
        cands.append((lab2con[label], "label"))
    if not cands:  # extraction-tolerant: split words, then wrapped labels (before fuzzy)
        ns = nospace(label)
        cm_ns = {nospace(k): v for k, v in cm.items()}
        for k in (nospace(key), ns):
            if k in cm_ns:
                cands.append((cm_ns[k], "nospace"))
                break
        lab_ns = {}
        for l, v in lab2con.items():
            lab_ns.setdefault(nospace(l), v)
        if not cands and ns in lab_ns:
            cands.append((lab_ns[ns], "nospace"))
        if not cands and len(ns) >= 6:  # wrapped label: the tail of exactly one caption
            tails = {v for l, v in lab_ns.items() if l != ns and l.endswith(ns)}
            if len(tails) == 1:
                cands.append((tails.pop(), "suffix"))
    hit = difflib.get_close_matches(label, list(lab2con), n=1, cutoff=0.8)
    if hit:
        cands.append((lab2con[hit[0]], "fuzzy"))
    seen = set()
    return [c for c in cands if not (c[0] in seen or seen.add(c[0]))]


# ------------------------------------------------------------------ 3. compare
def tolerance(decimals):
    if decimals in (None, "INF", ""):
        return 0.5
    return 0.5 * 10 ** (-int(decimals))


def compare(pdf_val, xbrl_val, decimals):
    if pdf_val is None or pd.isna(pdf_val):
        return "pdf_missing"
    if xbrl_val is None:
        return "xbrl_missing"
    tol = tolerance(decimals)
    if abs(pdf_val - xbrl_val) <= tol:
        return "match"
    if abs(abs(pdf_val) - abs(xbrl_val)) <= tol:
        return "sign"
    for k in (1e3, 1e6, 1e9):
        if abs(pdf_val * k - xbrl_val) <= max(tol, 0.5 * k):
            return f"scale_x{int(k)}"      # PDF value under-scaled
        if abs(pdf_val / k - xbrl_val) <= max(tol, 0.5):
            return f"scale_x1/{int(k)}"    # PDF value over-scaled (e.g. EPS multiplied)
    return "mismatch"


CAUSE = {  # Lab 11 triage table -> suggested cause (team confirms)
    "sign": "presentation: statement shows the value negated vs XBRL (sign policy)",
    "scale": "normalization: caption scale not applied or a missing row exception",
    "mismatch": "period alignment / column shift, or wrong concept (check mapping)",
    "pdf_missing": "table structure: row or column not extracted (see bake-off)",
    "xbrl_missing": "mapping: extension, dimensional or unmapped concept",
}


def pick_fact(facts, concept, member, period, kind, periods, form):
    f = facts[facts["concept"] == concept]
    f = f[f["dims"].str.endswith(f"={member}") & ~f["dims"].str.contains(";")] if member \
        else f[f["dims"] == ""]
    year = int(period.split("_")[0])
    if kind == "balance_sheet":
        f = f[f["instant"] & f["end"].apply(lambda d: d is not None and d.year == year)]
        return f.sort_values("end").iloc[-1] if len(f) else None
    f = f[~f["instant"] & f["end"].apply(lambda d: d is not None and d.year == year)]
    if f.empty:
        return None
    if form == "10-K":
        f = f[(f["days"] > 350) & (f["days"] < 380)]
        return f.iloc[0] if len(f) else None
    # 10-Q: first column of a year = quarter, second (suffix _2) = year-to-date
    f = f.sort_values("days")
    return f.iloc[0] if "_" not in period else f.iloc[-1]


BS_ZONES = (("totalcurrentassets", "current assets"), ("totalassets", ""),
            ("totalcurrentliabilities", "current liabilities"), ("totalliabilities", ""))


def infer_sections(cells, cm):
    """Restore lost balance sheet sections (10-Q traditional) from subtotal positions.

    A row keeps its extracted section only if the curated map uses it (whitespace
    removed); blank or garbled sections are inferred from the first subtotal at or
    after the row (rows are in table order; the damaged 10-Q table starts mid-sheet,
    so zones look forward). Rows after every subtotal get "", like AKAM's equity and
    non-current rows. Lines are keyed on (section, label): the same label can appear
    in both a current and a non-current position. Adds section_source."""
    known = {nospace(k.split(" > ")[0]) for k in cm if " > " in k}
    lines = list(dict.fromkeys(zip(cells["section"], cells["label"])))
    idx = {line: i for i, line in enumerate(lines)}
    pos = {}
    for s, l in lines:
        pos.setdefault(nospace(l), idx[(s, l)])

    def zone(line):
        for total, sec in BS_ZONES:
            if total in pos and idx[line] <= pos[total]:
                return sec
        return ""

    keep = cells["section"].map(lambda s: nospace(s) in known)
    cells["section"] = [s if k else zone((s, l)) for s, l, k
                        in zip(cells["section"], cells["label"], keep)]
    cells["section_source"] = keep.map({True: "extracted", False: "inferred"})
    return cells


def validate(stem, m, facts, curated, lab2con):
    out = []
    for path, folder in PATHS.items():
        for kind in STATEMENTS:
            allowed = set(facts.loc[facts["instant"] == (kind == "balance_sheet"), "concept"])
            lab2con_k = {lab: c for lab, c in lab2con.items() if c in allowed}
            f = folder / f"{stem}_{kind}.cells.csv"
            if not f.exists():
                out.append({"stem": stem, "path": path, "statement": kind, "status": "no_table"})
                continue
            cells = pd.read_csv(f, dtype={"section": str, "label": str, "period": str}).fillna(
                {"section": "", "label": ""})
            if kind == "balance_sheet":
                cells = infer_sections(cells, curated.get(kind, {}) or {})
            else:
                cells["section_source"] = "extracted"
            periods = list(dict.fromkeys(cells["period"]))
            for (sec, lab), g in cells.groupby(["section", "label"], sort=False):
                cands = map_label(kind, sec, lab, curated, lab2con_k)
                target, method = cands[0] if cands else (None, "unmapped")
                for t, meth in cands:  # first candidate the filing actually tagged
                    c_, m_ = parse_target(t)
                    if any(pick_fact(facts, c_, m_, p, kind, periods, m["form"]) is not None
                           for p in periods):
                        target, method = t, meth
                        break
                concept, member = parse_target(target) if target else (None, None)
                for _, c in g.iterrows():
                    fact = pick_fact(facts, concept, member, c["period"], kind, periods,
                                     m["form"]) if concept else None
                    xv = None if fact is None else fact["value"]
                    pv = None if pd.isna(c["value"]) else float(c["value"])
                    raw = str(c["raw"])
                    if pv is not None and pv > 0 and raw.startswith("(") and ")" not in raw:
                        pv = -pv  # clipped ")": the PDF shows the value in parentheses
                    st = compare(pv, xv, None if fact is None else fact["decimals"])
                    cause = "" if st == "match" else CAUSE.get(st.split("_x")[0], "")
                    out.append({"stem": stem, "path": path, "statement": kind, "section": sec,
                                "section_source": c["section_source"],
                                "label": lab, "period": c["period"], "raw": c["raw"],
                                "pdf_value": pv, "concept": target or "", "method": method,
                                "xbrl_value": xv, "status": st, "suggested_cause": cause})
    return out


def report(cmp: pd.DataFrame):
    rows = cmp[cmp["status"] != "no_table"].copy()
    rows["path"] = rows["path"].replace({"traditional": "trad."})
    rows["pdf_label"] = rows.apply(
        lambda row: f"{row['label']} ({row['stem']}, {row['statement']}, {row['period']})",
        axis=1)
    rows["diagnosis"] = rows.apply(
        lambda row: "—" if row["status"] == "match" else
        f"Not diagnosed; suggested cause: {row['suggested_cause']}; fix pending",
        axis=1)
    rows = rows.rename(columns={
        "path": "Path",
        "pdf_label": "PDF label",
        "concept": "Concept",
        "pdf_value": "PDF value",
        "xbrl_value": "XBRL value",
        "status": "Status",
        "method": "Mapping",
        "diagnosis": "Diagnosed cause / fix",
    })
    columns = ["Path", "PDF label", "Concept", "PDF value", "XBRL value",
               "Status", "Mapping", "Diagnosed cause / fix"]
    md = [rows[columns].to_markdown(index=False) if len(rows) else
          "| Path | PDF label | Concept | PDF value | XBRL value | Status | Mapping | "
          "Diagnosed cause / fix |\n|---|---|---|---:|---:|---|---|---|\n"
          "| — | No statement-line comparisons available | — | — | — | — | — | — |"]
    table = "\n".join(md)
    report = (f"# XBRL validation\n\n<!-- AUTO:START (generated, do not edit) -->\n"
              f"{table}\n<!-- AUTO:END -->\n")
    (REPORTS / "xbrl.md").write_text(report, encoding="utf-8")


def main():
    XBRL.mkdir(parents=True, exist_ok=True)
    curated = load_map()
    all_facts, cmp = [], []
    for stem, m in load_manifest().items():
        facts, lab2con = load_facts(ixbrl_file(m["accession"]), stem)
        all_facts.append(facts)
        cmp += validate(stem, m, facts, curated, lab2con)
        print(f"{stem}: {len(facts)} numeric facts")
    pd.concat(all_facts).to_csv(XBRL / "facts.csv", index=False)
    cmp = pd.DataFrame(cmp)
    cmp.to_csv(XBRL / "comparison.csv", index=False)
    report(cmp)
    ok = cmp[cmp["status"] != "no_table"]
    print(ok.groupby(["path", "statement"])["status"].apply(lambda s: f"{(s == 'match').mean():.1%}"))


if __name__ == "__main__":
    main()
