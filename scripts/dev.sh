#!/usr/bin/env bash
# Remote-only development. Does not start any inference services.
set -euo pipefail
cd "$(dirname "$0")/.."
children=()
cleanup() { for child in "${children[@]}"; do kill "$child" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
"${PYTHON:-python}" -m uvicorn vrag.api:app --host 127.0.0.1 --port 8000 &
children+=("$!")
npm --prefix web run dev -- --hostname 0.0.0.0 --port 7860 &
children+=("$!")
wait -n "${children[@]}"
