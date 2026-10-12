#!/usr/bin/env bash
# Serve the Gemma 4 12B QAT generator on vLLM (OpenAI-compatible API).
#
# Usage: serve/serve.sh [--port 8001] [--bg] [--mtp]
#   --bg   run detached; log + pidfile land in serve/logs/
#   --mtp  enable Multi-Token Prediction (speculative decoding with the -assistant drafter)
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${VRAG_GEN_MODEL:-google/gemma-4-12B-it-qat-w4a16-ct}"
ASSISTANT="${VRAG_GEN_ASSISTANT:-google/gemma-4-12B-it-assistant}"
PORT=8001
BG=0
MTP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --bg) BG=1; shift ;;
    --mtp) MTP=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Blackwell/VPN workarounds carried over from ~/projects/gemma-4-qat:
# - pin vLLM's distributed init to loopback (Tailscale IPs can hang startup)
# - FlashInfer's JIT sampler miscompiles on sm_120
# - sitecustomize patches a prometheus instrumentator crash that 500s every request
export VLLM_HOST_IP="${VLLM_HOST_IP:-127.0.0.1}"
export GLOO_SOCKET_IFNAME="${GLOO_SOCKET_IFNAME:-lo}"
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
export PYTHONPATH="$PWD/compat${PYTHONPATH:+:$PYTHONPATH}"

CMD=(uv run vllm serve "$MODEL"
  --host 127.0.0.1 --port "$PORT"
  --served-model-name gemma-4
  --max-model-len "${VRAG_GEN_MAX_LEN:-32768}"
  # leave room on the GPU for the EmbeddingGemma 2 API process
  --gpu-memory-utilization "${VRAG_GEN_GPU_UTIL:-0.55}"
  --limit-mm-per-prompt '{"image": 16, "video": 6, "audio": 6}'
  --allowed-local-media-path "$(cd .. && pwd)/data"
  --trust-remote-code)
if [[ "$MTP" == "1" ]]; then
  CMD+=(--speculative-config "{\"method\":\"mtp\",\"model\":\"$ASSISTANT\",\"num_speculative_tokens\":2}")
fi

mkdir -p logs
LOG="logs/vllm_${PORT}.log"
echo "==> ${CMD[*]}"
if [[ "$BG" == "1" ]]; then
  setsid "${CMD[@]}" >"$LOG" 2>&1 < /dev/null &
  echo $! > "logs/.vllm_${PORT}.pid"
  echo "==> started (pid $!). tail -f serve/$LOG ; stop with serve/stop.sh $PORT"
else
  exec "${CMD[@]}" 2>&1 | tee "$LOG"
fi
