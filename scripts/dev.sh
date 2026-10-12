#!/usr/bin/env bash
# Start everything for local use: vLLM (Gemma 4 12B, :8001), FastAPI (:8000), Next.js (:3000).
# Ctrl-C stops the API and web server; vLLM keeps running (stop with serve/stop.sh).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! curl -sf http://127.0.0.1:8001/v1/models >/dev/null; then
  serve/serve.sh --bg --mtp
  echo "==> waiting for vLLM (first start takes a few minutes)..."
  until curl -sf http://127.0.0.1:8001/v1/models >/dev/null; do sleep 5; done
fi

trap 'kill 0' EXIT
uv run vrag api &
(cd web && npm run dev) &
wait
