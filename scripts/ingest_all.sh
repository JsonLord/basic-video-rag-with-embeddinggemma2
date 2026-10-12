#!/usr/bin/env bash
# Ingest + transcribe everything in sams-videos/ (idempotent; finished steps are skipped).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run vrag ingest
uv run vrag transcribe
