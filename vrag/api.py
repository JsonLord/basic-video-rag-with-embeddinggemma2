"""FastAPI backend for the Next.js site. Run: uv run vrag api  (serves on :8000).

The Next.js dev server proxies /api/* and /media/* here (see web/next.config.ts).
"""

import json
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import remote as rag
from .config import DATA, DIMS, EXPERIMENTS_DIR, INDEX_DIR, VIDEOS_DIR, VIEWS
from .remote import encode_image_query, encode_query
from .providers import ProviderFailure
from .index import get_index

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Visual Mentor", version="1.0")
# Starlette's StaticFiles honours Range requests, so the browser can seek the mp4s.
app.mount("/media", StaticFiles(directory=VIDEOS_DIR), name="media")


def _video_meta(vdir: Path) -> dict:
    meta = json.loads((vdir / "meta.json").read_text())
    segs_path = vdir / "segments.json"
    meta["num_segments"] = len(json.loads(segs_path.read_text())) if segs_path.exists() else 0
    meta["thumb"] = f"/media/{vdir.name}/thumb.jpg"
    meta["video"] = f"/media/{vdir.name}/video.mp4"
    return meta


def _hit(h: dict) -> dict:
    return {**h, "frame": f"/media/{h['video_id']}/segments/{h['idx']:03d}.jpg"}


@app.get("/api/stats")
def stats() -> dict:
    manifest = json.loads((INDEX_DIR / "manifest.json").read_text()) if (INDEX_DIR / "manifest.json").exists() else {}
    idx = get_index()
    views_built = manifest.pop("views", {})
    return {
        **manifest,
        "views_built": views_built,
        "dims": DIMS,
        "views": idx.available_views,
        "view_descriptions": {**VIEWS, "hybrid": "Reciprocal rank fusion of text + video + audio rankings"},
        "storage": [{"dim": d, "bytes_per_view": idx.storage_bytes(d)} for d in DIMS],
        "total_duration_s": sum(json.loads((VIDEOS_DIR / vid / "meta.json").read_text())["duration"]
                                for vid in {s["video_id"] for s in idx.segments}),
    }


@app.get("/api/videos")
def videos() -> list[dict]:
    vids = [_video_meta(v) for v in VIDEOS_DIR.iterdir() if (v / "meta.json").exists()]
    return sorted(vids, key=lambda m: (m.get("channel_position") is None, m.get("channel_position") or 0, m["title"]))


@app.get("/api/videos/{video_id}")
def video(video_id: str) -> dict:
    if not video_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "invalid video ID")
    vdir = VIDEOS_DIR / video_id
    if not (vdir / "meta.json").exists():
        raise HTTPException(404, "unknown video")
    segs = json.loads((vdir / "segments.json").read_text()) if (vdir / "segments.json").exists() else []
    transcript = json.loads((vdir / "transcript.json").read_text()) if (vdir / "transcript.json").exists() else []
    return {
        **_video_meta(vdir),
        "segments": [{**s, "id": f"{video_id}_{s['idx']:03d}", "frame": f"/media/{video_id}/segments/{s['idx']:03d}.jpg"} for s in segs],
        "transcript": transcript,
        # Every engine's transcript, so the UI can compare them (e.g. whisper vs gemma).
        "transcripts": {engine: json.loads(p.read_text()) for engine, p in {p.stem.split(".", 1)[1]: p for p in vdir.glob("transcript.*.json")}.items()},
    }


def _check(view: str, dim: int) -> None:
    if view not in get_index().available_views:
        raise HTTPException(400, f"view must be one of {get_index().available_views}")
    if dim not in DIMS:
        raise HTTPException(400, f"dim must be one of {DIMS}")


@app.get("/api/search")
def search(q: str, view: str = "fused", dim: int = 768, k: int = Query(10, le=50), video_id: str | None = None) -> dict:
    _check(view, dim)
    t0 = time.time()
    qe = encode_query(q)
    t1 = time.time()
    hits = get_index().search(qe, view=view, dim=dim, k=k, video_id=video_id)
    return {"query": q, "view": view, "dim": dim, "hits": [_hit(h) for h in hits],
            "timing": {"embed_ms": round(1000 * (t1 - t0), 1), "search_ms": round(1000 * (time.time() - t1), 2)}}


@app.post("/api/search/image")
async def search_image(file: UploadFile = File(...), view: str = "frame", dim: int = 768, k: int = 10) -> dict:
    """Query by screenshot: the image is embedded with no prefix and searched against any view."""
    _check(view, dim)
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "q.png").suffix) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        qe = encode_image_query(tmp.name)
    hits = get_index().search(qe, view=view, dim=dim, k=k)
    return {"query": file.filename, "view": view, "dim": dim, "hits": [_hit(h) for h in hits]}


@app.get("/api/compare")
def compare(q: str, view: str = "fused", k: int = Query(5, le=20)) -> dict:
    """Same query at every MRL dim for one view, with overlap against the 768d results."""
    _check(view, 768)
    qe = encode_query(q)
    idx = get_index()
    columns = []
    base = None
    for dim in DIMS:
        hits = idx.search(qe, view=view, dim=dim, k=k)
        ids = [h["id"] for h in hits]
        base = base or ids
        columns.append({
            "dim": dim,
            "hits": [_hit(h) for h in hits],
            "overlap_with_768": len(set(ids) & set(base)) / k,
            "top1_matches_768": ids[:1] == base[:1],
            "bytes_per_view": idx.storage_bytes(dim),
        })
    return {"query": q, "view": view, "k": k, "columns": columns}


@app.get("/api/compare-views")
def compare_views(q: str, dim: int = 768, k: int = Query(5, le=20)) -> dict:
    """Same query across every embedding view at one dim."""
    _check("fused", dim)
    qe = encode_query(q)
    idx = get_index()
    return {"query": q, "dim": dim, "k": k,
            "columns": [{"view": v, "hits": [_hit(h) for h in idx.search(qe, view=v, dim=dim, k=k)]} for v in idx.available_views]}


class AskRequest(BaseModel):
    question: str
    view: str = "fused"
    dim: int = 768
    k: int = 4
    use_video: bool = True
    use_audio: bool = False


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    _check(req.view, req.dim)
    try:
        res = rag.answer(req.question, view=req.view, dim=req.dim, k=req.k, use_video=req.use_video, use_audio=req.use_audio)
    except Exception as e:  # generator offline etc.
        raise HTTPException(502, "generation unavailable; check provider configuration") from e
    res["clips"] = [_hit(c) for c in res["clips"]]
    return res


@app.get("/api/answers")
def answers(limit: int = 50) -> list[dict]:
    p = DATA / "answers" / "history.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()][-limit:][::-1]
    for r in rows:
        r["clips"] = [_hit(c) for c in r["clips"]]
    return rows


@app.get("/api/experiments")
def experiments(transcripts: str | None = Query(None, pattern="^[a-zA-Z0-9_-]+$")) -> dict:
    """Latest results, or the run over a specific transcript engine (?transcripts=whisper|gemma)."""
    p = EXPERIMENTS_DIR / (f"results.{transcripts}.json" if transcripts else "results.json")
    if not p.exists():
        raise HTTPException(404, "no experiment results yet - run `uv run vrag experiments`")
    res = json.loads(p.read_text())
    res["variants"] = sorted(f.name.split(".")[1] for f in EXPERIMENTS_DIR.glob("results.*.json"))
    segs = {s["id"]: s for s in get_index().segments}
    for q in res["per_query"]:
        s = segs.get(q["segment_id"])
        if s:
            q["segment"] = _hit({k: s[k] for k in ("id", "video_id", "title", "idx", "start", "end")})
    return res

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ProviderFailure)
async def provider_error(request: Request, exc: ProviderFailure):
    return JSONResponse(status_code=503, content={"detail": exc.code})
