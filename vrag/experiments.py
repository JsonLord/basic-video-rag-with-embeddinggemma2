"""Retrieval experiments: every (view x MRL dim) over the eval set, plus per-query ranks for the UI.

Writes data/experiments/results.json, plus results.<transcript engine>.json so runs over Whisper vs
Gemma transcripts can be compared side by side.
"""

import json
import time
from datetime import datetime, timezone

import numpy as np
from rich.console import Console
from rich.table import Table

from . import evalset
from .config import DIMS, EMBED_MODEL, EXPERIMENTS_DIR
from .embedder import get_model
from .index import get_index
from .segment import transcript_engine

console = Console()
KS = (1, 5, 10)


def metrics(ranks: list[int], video_top1: list[bool], neighbor_ranks: list[int]) -> dict:
    r = np.array(ranks)
    nb = np.array(neighbor_ranks)
    out = {f"recall@{k}": float((r <= k).mean()) for k in KS}
    out["mrr@10"] = float(np.where(r <= 10, 1.0 / r, 0.0).mean())
    out["neighbor_recall@5"] = float((nb <= 5).mean())
    out["video_hit@1"] = float(np.mean(video_top1))
    out["n"] = len(ranks)
    return out


def run() -> dict:
    queries = evalset.load()
    idx = get_index()
    console.print(f"[bold]Running experiments[/bold]: {len(queries)} queries x {idx.available_views} x {DIMS}")

    t0 = time.time()
    qembs = get_model().encode([q["query"] for q in queries], prompt_name="SearchQuery",
                               batch_size=64, convert_to_numpy=True).astype(np.float32)
    query_embed_ms = 1000 * (time.time() - t0) / len(queries)

    seg_pos = {s["id"]: i for i, s in enumerate(idx.segments)}
    per_query = [{**q, "ranks": {}} for q in queries]
    grid = []
    for view in idx.available_views:
        for dim in DIMS:
            ranks, video_top1, neighbor = [], [], []
            t1 = time.time()
            for qi, (q, qe) in enumerate(zip(queries, qembs)):
                order, _ = idx.rank(qe, view, dim)
                gold = seg_pos[q["segment_id"]]
                rank = int(np.where(order == gold)[0][0]) + 1
                gold_seg = idx.segments[gold]
                # Lenient: a hit on the adjacent segment of the same video still lands the viewer in the right spot.
                near = [r + 1 for r, i in enumerate(order[:10])
                        if idx.segments[i]["video_id"] == gold_seg["video_id"] and abs(idx.segments[i]["idx"] - gold_seg["idx"]) <= 1]
                ranks.append(rank)
                neighbor.append(near[0] if near else 10**6)
                video_top1.append(idx.segments[order[0]]["video_id"] == q["video_id"])
                per_query[qi]["ranks"][f"{view}@{dim}"] = rank
            search_ms = 1000 * (time.time() - t1) / len(queries)
            for qtype in ("all", "spoken", "visual"):
                sel = [i for i, q in enumerate(queries) if qtype == "all" or q["type"] == qtype]
                if not sel:
                    continue
                grid.append({
                    "view": view, "dim": dim, "query_type": qtype,
                    **metrics([ranks[i] for i in sel], [video_top1[i] for i in sel], [neighbor[i] for i in sel]),
                    "search_ms": round(search_ms, 3),
                })

    views_count = len([v for v in idx.available_views if v != "hybrid"])
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": EMBED_MODEL,
        "transcripts": transcript_engine(),
        "num_segments": len(idx.segments),
        "num_queries": len(queries),
        "query_types": {t: sum(q["type"] == t for q in queries) for t in ("spoken", "visual")},
        "query_embed_ms": round(query_embed_ms, 2),
        "dims": DIMS,
        "views": idx.available_views,
        "storage": [{"dim": d, "bytes_per_vector": d * 4, "bytes_per_view": idx.storage_bytes(d),
                     "bytes_all_views": idx.storage_bytes(d) * views_count} for d in DIMS],
        "grid": grid,
        "per_query": per_query,
    }
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    (EXPERIMENTS_DIR / "results.json").write_text(json.dumps(result, indent=1))
    (EXPERIMENTS_DIR / f"results.{result['transcripts']}.json").write_text(json.dumps(result, indent=1))
    _print(result)
    return result


def _print(result: dict) -> None:
    for qtype in ("all", "spoken", "visual"):
        t = Table(title=f"recall@5 / MRR@10 - {qtype} queries")
        t.add_column("view")
        for d in result["dims"]:
            t.add_column(f"{d}d", justify="right")
        for view in result["views"]:
            cells = []
            for d in result["dims"]:
                row = next((g for g in result["grid"] if g["view"] == view and g["dim"] == d and g["query_type"] == qtype), None)
                cells.append(f"{row['recall@5']:.2f} / {row['mrr@10']:.2f}" if row else "-")
            t.add_row(view, *cells)
        console.print(t)
