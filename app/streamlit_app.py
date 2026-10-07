"""LANTERN Explorer -- a Streamlit frontend for the LANTERN API.

Run locally (with the API already running):

    LANTERN_API_URL=http://127.0.0.1:8000 streamlit run app/streamlit_app.py

On Streamlit Community Cloud set ``LANTERN_API_URL`` in the app's secrets /
environment to the deployed backend URL (e.g. your Replit or Vercel domain).
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

DEFAULT_API = os.environ.get("LANTERN_API_URL", "http://127.0.0.1:8000")
TIMEOUT = float(os.environ.get("LANTERN_API_TIMEOUT", "30"))

st.set_page_config(page_title="LANTERN Explorer", page_icon="🏮", layout="wide")


# --------------------------------------------------------------------------- #
# API client
# --------------------------------------------------------------------------- #
class ApiError(RuntimeError):
    pass


def base_url() -> str:
    return st.session_state.get("api_url", DEFAULT_API).rstrip("/")


@st.cache_data(show_spinner=False, ttl=60)
def _get(url: str, params: tuple[tuple[str, object], ...] = ()) -> object:
    resp = requests.get(url, params=dict(params), timeout=TIMEOUT)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001 - any non-JSON error body
            detail = resp.text
        raise ApiError(f"{resp.status_code} {detail}")
    return resp.json()


def api(path: str, **params) -> object:
    clean = tuple((k, v) for k, v in params.items() if v is not None)
    return _get(f"{base_url()}{path}", clean)


def banner(message: str, kind: str = "error") -> None:
    {"error": st.error, "warning": st.warning, "info": st.info}[kind](message)


# --------------------------------------------------------------------------- #
# Sidebar: connection + filing selection
# --------------------------------------------------------------------------- #
st.sidebar.title("🏮 LANTERN Explorer")
st.session_state.setdefault("api_url", DEFAULT_API)
st.sidebar.text_input("API base URL", key="api_url")

health: dict | None = None
try:
    health = api("/health")
    st.sidebar.success(f"API v{health['version']} · {health['corpus']['filings']} filings")
    st.sidebar.caption(f"data root: `{health['data_root']}`")
except (ApiError, requests.RequestException) as exc:
    banner(
        f"Can't reach the API at `{base_url()}`.\n\n"
        f"Start it with `uvicorn src.api.main:app --reload`, then reload "
        f"(details: {exc})"
    )
    st.stop()

filings: list[dict] = api("/filings")
labels = {f"{f['stem']}  ·  {f['form']} {f['fiscal_period']} {f['fiscal_year']}": f["stem"]
          for f in filings}
choice = st.sidebar.selectbox("Filing", list(labels) or ["(none)"])
stem = labels.get(choice)

if stem is None:
    banner("The corpus is empty. Run the pipeline (or `python -m src.api.build_bundle`).")
    st.stop()


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
detail = api(f"/filings/{stem}")
st.title("Project LANTERN Explorer")
st.caption(
    f"**{detail.get('company')}** · {detail.get('form')} "
    f"{detail.get('fiscal_period')} {detail.get('fiscal_year')} · "
    f"CIK {detail.get('cik')} · accession `{detail.get('doc_id')}`"
)

overview_tab, document_tab, blocks_tab, tables_tab, xbrl_tab, search_tab, metrics_tab = st.tabs(
    ["Overview", "Document", "Blocks", "Tables", "XBRL", "Search", "Metrics"]
)


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
with overview_tab:
    cols = st.columns(6)
    cols[0].metric("Pages", detail["pages"])
    cols[1].metric("Blocks", f"{detail['blocks']:,}")
    cols[2].metric("Sections", detail["sections"])
    cols[3].metric("Tables", detail["table_count"])
    cols[4].metric("XBRL facts", f"{detail['xbrl_facts']:,}")
    cols[5].metric("OCR blocks", f"{detail['ocr_share']:.1%}")

    st.subheader("Section map")
    sections_df = pd.DataFrame(detail["section_list"])
    if not sections_df.empty:
        st.dataframe(
            sections_df.rename(columns={
                "section": "Section", "first_page": "First page",
                "last_page": "Last page", "blocks": "Blocks"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No section headings were detected for this filing.")

    with st.expander("Format sizes (Part 6)"):
        formats = api("/metrics")["format_sizes"]
        st.dataframe(pd.DataFrame(formats), use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #
with document_tab:
    md = api(f"/filings/{stem}/markdown")
    left, right = st.columns([3, 1])
    left.download_button(
        "⬇️ Download Markdown", md["markdown"],
        file_name=f"{stem}.md", mime="text/markdown", use_container_width=True)
    render = right.toggle("Render full document", value=False,
                          help="Large filings are shown as plain text by default.")
    if render:
        st.markdown(md["markdown"])
    else:
        st.caption(f"{md['characters']:,} characters — preview below (first 20,000).")
        st.text_area("Markdown", md["markdown"][:20_000], height=480,
                     label_visibility="collapsed")

    st.divider()
    st.subheader("Page text")
    page_no = st.selectbox("Page", detail["pages_list"])
    page = api(f"/filings/{stem}/pages/{page_no}")
    st.text(page["text"] or "(no text on this page)")


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #
with blocks_tab:
    f1, f2, f3, f4 = st.columns(4)
    page_filter = f1.selectbox("Page", [None, *detail["pages_list"]])
    type_filter = f2.selectbox(
        "Block type", [None, "Title", "Text", "List", "Table", "Figure", "Footnote"])
    section_filter = f3.text_input("Section contains")
    text_filter = f4.text_input("Text contains")

    page_data = api(f"/filings/{stem}/blocks", page=page_filter, block_type=type_filter,
                    section=section_filter or None, q=text_filter or None, limit=500)
    st.caption(f"{page_data['total']:,} matching blocks")
    blocks_df = pd.DataFrame(page_data["items"])
    if not blocks_df.empty:
        show = [c for c in ["block_id", "page", "block_type", "section", "text", "extractor",
                            "ocr", "bbox"] if c in blocks_df.columns]
        st.dataframe(blocks_df[show], use_container_width=True, hide_index=True, height=340)
        pick = st.selectbox("Inspect block", blocks_df["block_id"])
        row = blocks_df[blocks_df["block_id"] == pick].iloc[0].to_dict()
        st.json(row, expanded=True)
    else:
        st.info("No blocks match those filters.")


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
with tables_tab:
    log = api("/tables", stem=stem, limit=2000)
    accepted_only = st.toggle("Accepted only", value=False)
    rows = [r for r in log if (r.get("accepted") if accepted_only else True)]
    st.caption(f"{len(rows)} tables")
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=280)

    names = api(f"/tables/{stem}")
    if names:
        name = st.selectbox("Open a clean grid", names)
        grid = api(f"/tables/{stem}/{name}")
        st.dataframe(pd.DataFrame(grid["rows"], columns=grid["columns"]),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No clean grids for this filing.")


# --------------------------------------------------------------------------- #
# XBRL
# --------------------------------------------------------------------------- #
with xbrl_tab:
    summary_rows = [r for r in api("/xbrl/summary") if r.get("stem") == stem]
    if summary_rows:
        rate_df = pd.DataFrame(summary_rows).set_index("statement")["match_rate"]
        st.bar_chart(rate_df, height=220)
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    st.subheader("PDF vs XBRL comparison")
    status = st.selectbox("Status", [None, "match", "mismatch"])
    comp = api("/xbrl/comparison", stem=stem, status=status, limit=500)
    st.caption(f"{len(comp)} rows")
    if comp:
        st.dataframe(pd.DataFrame(comp), use_container_width=True, hide_index=True, height=280)

    st.subheader("Facts")
    query = st.text_input("Filter facts by concept or label", key="fact_q")
    facts = api("/xbrl/facts", stem=stem, q=query or None, limit=200)
    st.caption(f"{facts['total']:,} facts")
    if facts["items"]:
        st.dataframe(pd.DataFrame(facts["items"]), use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
with search_tab:
    q = st.text_input("Search the corpus", placeholder="e.g. revenue, cyber, dividend")
    scope = st.radio("Scope", ["This filing", "All filings"], horizontal=True)
    if q:
        try:
            out = api("/search", q=q, stem=stem if scope == "This filing" else None, limit=100)
            st.caption(f"{out['total']} hits" + (" (truncated)" if out["truncated"] else ""))
            for hit in out["items"]:
                st.markdown(f"**{hit['stem']} · p{hit['page']} · {hit.get('section') or '—'}**  "
                            f"`{hit['block_id']}`")
                st.write(hit["snippet"])
                st.divider()
        except ApiError as exc:
            banner(str(exc))


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
with metrics_tab:
    payload = api("/metrics")
    st.subheader("Evaluation metrics (Part 9)")
    st.json(payload["metrics"], expanded=True)

    st.subheader("Benchmarks (Part 10)")
    bench = pd.DataFrame(api("/benchmarks", limit=10000))
    if not bench.empty:
        per_stage = bench.groupby("stage")["seconds"].mean().sort_values()
        st.bar_chart(per_stage, height=240)
        st.dataframe(
            bench.groupby("stage")[["seconds", "peak_rss_mb"]].mean().round(3),
            use_container_width=True)
    else:
        st.info("No benchmark data bundled.")

    st.subheader("Reports")
    st.dataframe(pd.DataFrame(payload["reports"]), use_container_width=True, hide_index=True)
