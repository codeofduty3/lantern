"""Freeze a small, self-contained ``data/serve`` bundle for deployment.

The pipeline's outputs live under DVC (``dvc pull``), which Replit/Vercel can't
do without credentials. This script copies just the artifacts the API serves
into ``data/serve`` so the backend is portable:

    python -m src.api.build_bundle

``src/api/store.py`` prefers ``data/serve`` when it exists, so the same code
runs locally against the DVC data and remotely against the bundle.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from common import BENCH, EXPORT, REPORTS, TABLES, XBRL  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "data" / "serve"


def _copy(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst.stat().st_size


def build(out: Path = DEFAULT_OUT, force: bool = False) -> dict:
    if out.exists() and not force:
        raise SystemExit(f"{out} already exists; pass --force to overwrite")
    if out.exists():
        shutil.rmtree(out)

    total = 0
    files = 0

    # Part 5/6: provenance blocks + Markdown, plus the format-size table.
    for path in sorted(EXPORT.glob("*.jsonl")):
        total += _copy(path, out / "export" / path.name); files += 1
    for path in sorted(EXPORT.glob("*.md")):
        total += _copy(path, out / "export" / path.name); files += 1
    if (EXPORT / "format_sizes.csv").exists():
        total += _copy(EXPORT / "format_sizes.csv", out / "export" / "format_sizes.csv"); files += 1

    # Part 2: the extraction log and only the clean grids (skip raw/cells dumps).
    if (TABLES / "tables_log.csv").exists():
        total += _copy(TABLES / "tables_log.csv", out / "tables" / "tables_log.csv"); files += 1
    for path in sorted(TABLES.glob("*.clean.csv")):
        total += _copy(path, out / "tables" / path.name); files += 1

    # Part 11: XBRL facts and the PDF-vs-XBRL comparison.
    for name in ("facts.csv", "comparison.csv"):
        if (XBRL / name).exists():
            total += _copy(XBRL / name, out / "xbrl" / name); files += 1

    # Part 10: benchmark timings (git-tracked already, but keep the bundle whole).
    for path in sorted(BENCH.glob("*.csv")):
        total += _copy(path, out / "bench" / path.name); files += 1

    # Parts 9-10: the reports the /metrics endpoint links to. Bundle every
    # top-level report (metrics.json plus reports/*.md) so a new report never
    # silently drops out of the bundle -- and out of the UI's Reports list.
    for path in [REPORTS / "metrics.json", *sorted(REPORTS.glob("*.md"))]:
        if path.exists():
            total += _copy(path, out / "reports" / path.name); files += 1

    return {"out": str(out), "files": files, "bytes": total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true", help="overwrite an existing bundle")
    args = parser.parse_args()
    stats = build(args.out, force=args.force)
    print(f"wrote {stats['files']} files ({stats['bytes'] / 1e6:.2f} MB) -> {stats['out']}")


if __name__ == "__main__":
    main()
