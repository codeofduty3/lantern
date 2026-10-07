# Part 12 - Serving layer (API + UI)

The pipeline in `src/` produces a validated corpus. This part puts a thin,
read-only **backend** and a **frontend** in front of it so the corpus can be
browsed and demoed without re-running DVC:

```
        ┌───────────────┐   HTTP/JSON   ┌────────────────────┐   reads   ┌──────────────────┐
        │  Streamlit UI │ ────────────▶ │  FastAPI backend   │ ────────▶ │ data/ (or bundle)│
        │  app/…         │              │  src/api/main.py   │           │ export, tables,  │
        │  (frontend)   │ ◀──────────── │  Swagger at /docs  │ ◀──────── │ xbrl, reports    │
        └───────────────┘               └────────────────────┘           └──────────────────┘
```

Nothing here writes to the pipeline outputs; the API only reads them.

## Why two processes

Streamlit is a server that renders the UI, and the FastAPI app is a normal HTTP
API. Keeping them apart means the API can be hosted where a long-lived server is
natural (Replit, a VM, Vercel serverless) and the UI can be hosted where Python
web apps are natural (Streamlit Community Cloud, Replit, a VM).

## Run it locally

The serving stack has its own dependencies so it never disturbs the pipeline's
pinned environment (`pandas==3.0.6`, `requests==2.34.2`, ...):

```bash
python3.11 -m venv .venv-serve && source .venv-serve/bin/activate
pip install -r src/api/requirements.txt -r app/requirements.txt

# Terminal 1 - backend (Swagger UI at http://127.0.0.1:8000/docs)
uvicorn src.api.main:app --reload

# Terminal 2 - frontend
LANTERN_API_URL=http://127.0.0.1:8000 streamlit run app/streamlit_app.py
```

Or with the helper targets: `make api` and `make ui`.

## Endpoints

The interactive Swagger UI is served at `/docs`; every operation there has a
working **Try it out** button, and the raw schema is at `/openapi.json`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + corpus inventory |
| GET | `/filings` | One row per filing (pages, blocks, OCR share, tables) |
| GET | `/filings/{stem}` | Filing detail + section map |
| GET | `/filings/{stem}/sections` | Ordered section spans |
| GET | `/filings/{stem}/blocks` | Query provenance blocks (page/type/section/text/OCR) |
| GET | `/filings/{stem}/pages/{page}` | Every block on one page |
| GET | `/filings/{stem}/markdown` | The filing as section Markdown |
| GET | `/tables` | Table extraction log (Part 2) |
| GET | `/tables/{stem}` | Clean grids available for a filing |
| GET | `/tables/{stem}/{name}` | One clean grid (statement id or `p0027_t1`) |
| GET | `/xbrl/facts` | Validated XBRL facts (Part 11) |
| GET | `/xbrl/comparison` | PDF value vs XBRL value |
| GET | `/xbrl/summary` | Match rate per statement |
| GET | `/metrics` | `reports/metrics.json`, format sizes, report index (Part 9) |
| GET | `/benchmarks` | Per-page timings (Part 10) |
| GET | `/search` | Case-insensitive full-text search with provenance |

Example:

```bash
curl "http://127.0.0.1:8000/filings/AKAM_10K_20241231/blocks?page=53&limit=5"
curl "http://127.0.0.1:8000/search?q=revenue&limit=3"
```

## Deployment bundle

The pipeline data under `data/` is DVC-managed and git-ignored, so a fresh clone
has no corpus. `src/api/build_bundle.py` copies just what the API serves into
`data/serve` (a few MB) so the backend is portable to hosts that cannot run DVC:

```bash
python -m src.api.build_bundle          # add --force to refresh
```

`src/api/store.py` reads, in order: `$LANTERN_DATA_ROOT`, then `data/serve` when
present, then the repository `data/`. So the same code runs against DVC data
locally and against the bundle remotely.

## Deploy the API on Replit (Swagger there)

This is the requested path: the repo already carries `.replit` + `replit.nix`,
so importing the project and pressing **Run** starts
`bash run_api.sh` → `uvicorn` on `0.0.0.0:$PORT`.

1. In Replit: **Create Repl → Import from GitHub →** `codeofduty3/lantern` (or
   upload the folder).
2. Replit installs `replit.nix`; run the serving deps once in the Shell:

   ```bash
   pip install -r src/api/requirements.txt
   ```

3. Press **Run**. Replit exposes the port and `run_api.sh` binds `0.0.0.0`.
4. Open `https://<your-repl>.<user>.repl.co/docs` - the Swagger UI is live and
   the endpoints execute against the bundled corpus directly from that page.

`Procfile` (`web: bash run_api.sh`) covers Replit Deployments and other
Procfile-based hosts.

## Deploy the API on Vercel (alternative)

`vercel.json` + `api/index.py` expose the same FastAPI app as a Python
serverless function, and a small middleware restores the original request path
after Vercel's rewrite:

```bash
npm i -g vercel      # once
vercel               # preview
vercel --prod        # production
```

Vercel serves the function under `/api`, so the Swagger UI is at
`https://<project>.vercel.app/api/docs` (links inside it are rewritten to match).

## Deploy the frontend

Streamlit is a long-running Python server, so **Vercel cannot host it** - use one
of these instead. All of them just need the API URL.

**Streamlit Community Cloud** (one click, free):

1. <https://share.streamlit.io> → **New app** → pick `codeofduty3/lantern`.
2. Main file path: `app/streamlit_app.py` (its adjacent `app/requirements.txt`
   is used, not the heavy root one).
3. In **Advanced settings → Secrets** add:

   ```toml
   LANTERN_API_URL = "https://<your-repl>.repl.co"
   ```

**Replit / Hugging Face Spaces / any VM**: run
`streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
with `LANTERN_API_URL` set in the environment.

## Configuration

| Variable | Where | Default | Meaning |
|---|---|---|---|
| `LANTERN_API_URL` | frontend | `http://127.0.0.1:8000` | Backend base URL |
| `LANTERN_API_TIMEOUT` | frontend | `30` | Per-request timeout (s) |
| `LANTERN_DATA_ROOT` | backend | auto | Override the corpus location |
| `LANTERN_CORS_ORIGINS` | backend | `*` | Comma-separated allowed origins |
| `PORT` | backend | `8000` | Bind port (set by Replit/Vercel) |

For a locked-down deployment set `LANTERN_CORS_ORIGINS` to the frontend origin
instead of `*`.

## Tests

`tests/test_api.py` covers the OpenAPI contract, the Swagger UI, and the corpus
endpoints. It runs in the smoke job (which installs `fastapi` + `httpx`) and
skips the corpus assertions when `data/export` is empty:

```bash
pytest -q tests/test_api.py
```

## Troubleshooting

- **UI shows "Can't reach the API"** - the backend isn't running or
  `LANTERN_API_URL` points at the wrong host. Open `<api>/health` to check.
- **`/health` says 0 filings** - the corpus is missing. Run `dvc pull`, or build
  the bundle with `python -m src.api.build_bundle`.
- **`pip install` wants to downgrade pandas/requests** - you are installing into
  the pipeline venv. Use the separate `.venv-serve` described above.
