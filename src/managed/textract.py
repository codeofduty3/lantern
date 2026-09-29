"""AWS Textract client + mapping of its block graph into LANTERN structures."""
import boto3
import pandas as pd


def analyze(page_bytes: bytes, cfg: dict) -> dict:
    """Sync AnalyzeDocument accepts a single-page PDF. TABLES meter: see pricing in params."""
    tx = boto3.client("textract", region_name=cfg.get("region", "us-east-1"))
    r = tx.analyze_document(Document={"Bytes": page_bytes}, FeatureTypes=["TABLES"])
    r.pop("ResponseMetadata", None)
    return r


def _bbox(b, w_pt, h_pt):
    g = b["Geometry"]["BoundingBox"]  # ratios of page size, top-left origin
    return [g["Left"] * w_pt, g["Top"] * h_pt, (g["Left"] + g["Width"]) * w_pt,
            (g["Top"] + g["Height"]) * h_pt]


def lines(resp: dict, w_pt: float, h_pt: float) -> list:
    return [{"text": b["Text"], "conf": b.get("Confidence"), "bbox": _bbox(b, w_pt, h_pt)}
            for b in resp.get("Blocks", []) if b["BlockType"] == "LINE"]


def text(resp: dict) -> str:
    return "\n".join(b["Text"] for b in resp.get("Blocks", []) if b["BlockType"] == "LINE")


def mean_conf(resp: dict) -> float:
    c = [b["Confidence"] for b in resp.get("Blocks", []) if b["BlockType"] == "WORD"]
    return sum(c) / len(c) if c else 0.0


def tables(resp: dict) -> list:
    """Each TABLE as a DataFrame of cell strings (row/col indices from Textract)."""
    by_id = {b["Id"]: b for b in resp.get("Blocks", [])}

    def kids(b, kind):
        for rel in b.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for i in rel["Ids"]:
                    if by_id[i]["BlockType"] == kind:
                        yield by_id[i]

    out = []
    for t in (b for b in by_id.values() if b["BlockType"] == "TABLE"):
        cells = list(kids(t, "CELL"))
        if not cells:
            continue
        nr = max(c["RowIndex"] for c in cells)
        nc = max(c["ColumnIndex"] for c in cells)
        grid = [[""] * nc for _ in range(nr)]
        for c in cells:
            grid[c["RowIndex"] - 1][c["ColumnIndex"] - 1] = " ".join(
                w["Text"] for w in kids(c, "WORD"))
        out.append(pd.DataFrame(grid))
    return out
