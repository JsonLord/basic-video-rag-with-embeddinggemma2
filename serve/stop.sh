#!/usr/bin/env bash
# Stop a backgrounded vLLM server. Usage: serve/stop.sh [port]
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8001}"
PIDFILE="logs/.vllm_${PORT}.pid"
if [[ -f "$PIDFILE" ]]; then
  PID="$(cat "$PIDFILE")"
  kill -TERM -- "-$(ps -o pgid= "$PID" | tr -d ' ')" 2>/dev/null || kill "$PID" 2>/dev/null || true
  rm -f "$PIDFILE"
  echo "stopped $PID"
else
  echo "no pidfile for port $PORT"
fi
