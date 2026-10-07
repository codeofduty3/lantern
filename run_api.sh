#!/usr/bin/env bash
# Start the LANTERN API. Used locally, on Replit (.replit) and by Procfile hosts.
set -euo pipefail

# Replit (and most PaaS) inject $PORT; fall back to 8000 for local use.
PORT="${PORT:-8000}"

exec python -m uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips '*'
