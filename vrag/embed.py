"""Embed every segment under every view and write data/index/<view>.npy (N x 768, float32, unit-norm)."""

import json
import time
from datetime import datetime, timezone

import numpy as np
from rich.console import Console

from .config import EMBED_MODEL, INDEX_DIR, VIEWS
from .embedder import encode_view
from .segment import transcript_engine

console = Console()

BATCH = {"text": 32, "frame": 16, "audio": 16, "video": 4, "fused": 4}


def run(views: list[str] | None = None, force: bool = False) -> None:
    segs = json.loads((INDEX_DIR / "segments.json").read_text())
    manifest_path = INDEX_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"views": {}}
    for view in views or list(VIEWS):
        out = INDEX_DIR / f"{view}.npy"
        if out.exists() and not force and np.load(out).shape[0] == len(segs):
            console.print(f"  {view}: cached")
            continue
        console.print(f"[bold]Embedding view '{view}'[/bold] for {len(segs)} segments")
        t0 = time.time()
        embs = encode_view(view, segs, BATCH[view])
        elapsed = time.time() - t0
        if not np.isfinite(embs).all():
            raise RuntimeError(f"non-finite embeddings in view {view}")
        np.save(out, embs)
        manifest["views"][view] = {
            "description": VIEWS[view],
            "count": int(embs.shape[0]),
            "dim": int(embs.shape[1]),
            "seconds": round(elapsed, 1),
            "ms_per_segment": round(1000 * elapsed / len(segs), 1),
        }
        console.print(f"  {view}: {embs.shape} in {elapsed:.0f}s")
    manifest.update({
        "model": EMBED_MODEL,
        "segments": len(segs),
        "videos": len({s["video_id"] for s in segs}),
        "transcripts": transcript_engine(),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2))
