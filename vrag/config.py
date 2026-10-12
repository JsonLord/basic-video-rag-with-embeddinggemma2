"""Paths and knobs shared across the pipeline. Override any of these with VRAG_* env vars."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("VRAG_DATA", ROOT / "data"))
VIDEOS_DIR = DATA / "videos"
INDEX_DIR = DATA / "index"
EVAL_DIR = DATA / "eval"
EXPERIMENTS_DIR = DATA / "experiments"

CHANNEL_URL = os.environ.get("VRAG_CHANNEL", "https://www.youtube.com/@samwitteveenai/videos")
NUM_VIDEOS = int(os.environ.get("VRAG_NUM_VIDEOS", 15))

EMBED_MODEL = os.environ.get("VRAG_EMBED_MODEL", "google/embeddinggemma-2")
GEN_BASE_URL = os.environ.get("VRAG_GEN_BASE_URL", "http://127.0.0.1:8001/v1")
GEN_MODEL = os.environ.get("VRAG_GEN_MODEL_NAME", "gemma-4")

# Speech-to-text engine: "gemma" (Gemma 4 12B via the vLLM server) or "whisper" (local).
ASR_ENGINE = os.environ.get("VRAG_ASR", "gemma")

# Segments target ~30s and snap to caption boundaries. At 1fps that's ~30 frames * 140
# tokens + 30s * 25 audio tokens + transcript, comfortably inside the 8,192-token window.
SEGMENT_TARGET_S = float(os.environ.get("VRAG_SEGMENT_S", 30))
SEGMENT_MIN_S = 12.0

# MRL dimensions EmbeddingGemma 2 is trained for.
DIMS = [768, 512, 256, 128]

# Each segment gets one embedding per "view" so we can compare what actually helps retrieval.
VIEWS = {
    "text": "Transcript only (title + caption text)",
    "frame": "Single keyframe image from the middle of the segment",
    "video": "Video frames only at 1fps (no audio, no text)",
    "audio": "Raw audio only (16kHz mono), no transcript",
    "fused": "Transcript + video + audio interleaved into one embedding",
}
