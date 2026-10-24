"""FastAPI backend for the Next.js site. Run: uv run vrag api  (serves on :8000).

The Next.js dev server proxies /api/* and /media/* here (see web/next.config.ts).
"""

import json
import asyncio
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from .mentor_api import user
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import remote as rag
from .config import DATA, DIMS, EXPERIMENTS_DIR, INDEX_DIR, VIDEOS_DIR, VIEWS
from .providers import ProviderFailure
from .index import get_index

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
@asynccontextmanager
async def lifespan(app):
    from .mentor_api import session_cleanup
    cleanup = asyncio.create_task(session_cleanup())
    from .jobs import worker
    jobs_task = asyncio.create_task(worker())
    from .backup.service import configured, queue
    backup_task = asyncio.create_task(queue.run()) if configured() else None
    from .mentor_state import recover_turns
    from .research_jobs import coordinator
    recover_turns()
    research_task=asyncio.create_task(coordinator())
    try:
        yield
    finally:
        from .conversation import shutdown
        await shutdown()
        research_task.cancel()
        await asyncio.gather(research_task,return_exceptions=True)
        if backup_task:
            backup_task.cancel()
            await asyncio.gather(backup_task, return_exceptions=True)
        cleanup.cancel()
        jobs_task.cancel()
        await asyncio.gather(cleanup, jobs_task, return_exceptions=True)

app = FastAPI(title="Visual Mentor", version="1.0", lifespan=lifespan)
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
def stats(owner=Depends(user)) -> dict:
    manifest_path=get_index().path/'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    idx = get_index()
    views_built = manifest.pop("views", {})
    return {
        **manifest,
        "views_built": views_built,
        "limitations": "Remote text embeddings support text only. Image/video/audio/fused search needs a verified compatible multimodal adapter and index. Legacy indexes require explicit re-embedding.",
        "dims": idx.dims,
        "views": idx.available_views,
        "view_descriptions": {**VIEWS, "hybrid": "Reciprocal rank fusion of text + video + audio rankings"},
        "storage": [{"dim": d, "bytes_per_view": idx.storage_bytes(d)} for d in idx.dims],
        "total_duration_s": sum(json.loads((VIDEOS_DIR / vid / "meta.json").read_text())["duration"]
                                for vid in {s["video_id"] for s in idx.segments}),
    }


@app.get("/api/videos")
def videos(owner=Depends(user)) -> list[dict]:
    vids = [_video_meta(v) for v in VIDEOS_DIR.iterdir() if (v / "meta.json").exists()]
    return sorted(vids, key=lambda m: (m.get("channel_position") is None, m.get("channel_position") or 0, m["title"]))


@app.get("/api/videos/{video_id}")
def video(video_id: str, owner=Depends(user)) -> dict:
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
    if not get_index().available_views:
        raise HTTPException(409, "No index loaded; configure remote embeddings and build a separate versioned index")
    if view not in get_index().available_views:
        raise HTTPException(400, f"view must be one of {get_index().available_views}")
    if dim not in get_index().dims:
        raise HTTPException(400, f"dim must be one of {get_index().dims}; this model does not support arbitrary MRL truncation")


@app.get("/api/search")
async def search(q: str = Query(max_length=8000), view: str = "text", dim: int = 768, k: int = Query(10, ge=1, le=50), video_id: str | None = None, owner=Depends(user)) -> dict:
    _check(view, dim)
    t0 = time.time()
    qe = await rag.query(q)
    t1 = time.time()
    hits = get_index().search(qe, view=view, dim=dim, k=k, video_id=video_id)
    return {"query": q, "view": view, "dim": dim, "hits": [_hit(h) for h in hits],
            "timing": {"embed_ms": round(1000 * (t1 - t0), 1), "search_ms": round(1000 * (time.time() - t1), 2)}}


@app.post("/api/search/image")
async def search_image(file: UploadFile = File(...), view: str = "frame", dim: int = 768, k: int = Query(10, ge=1, le=50), owner=Depends(user)) -> dict:
    """Query by screenshot: the image is embedded with no prefix and searched against any view."""
    raise HTTPException(409, "Remote text embeddings do not support image queries; a verified multimodal adapter is required")


@app.get("/api/compare")
async def compare(q: str = Query(max_length=8000), view: str = "text", k: int = Query(5, ge=1, le=20), owner=Depends(user)) -> dict:
    """Same query at every MRL dim for one view, with overlap against the 768d results."""
    _check(view, 768)
    qe = await rag.query(q)
    idx = get_index()
    columns = []
    base = None
    for dim in idx.dims:
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
async def compare_views(q: str = Query(max_length=8000), dim: int = 768, k: int = Query(5, ge=1, le=20), owner=Depends(user)) -> dict:
    """Same query across every embedding view at one dim."""
    _check("text", dim)
    qe = await rag.query(q)
    idx = get_index()
    return {"query": q, "dim": dim, "k": k,
            "columns": [{"view": v, "hits": [_hit(h) for h in idx.search(qe, view=v, dim=dim, k=k)]} for v in idx.available_views]}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    view: str = "text"
    dim: int = 768
    k: int = Field(default=4, ge=1, le=8)
    use_video: bool = True
    use_audio: bool = False


@app.post("/api/ask")
async def ask(req: AskRequest, owner=Depends(user)) -> dict:
    _check(req.view, req.dim)
    try:
        res = await rag._answer(req.question, view=req.view, dim=req.dim, k=req.k, use_video=req.use_video, use_audio=req.use_audio)
    except ProviderFailure:
        raise
    except Exception as e:  # generator offline etc.
        raise HTTPException(502, "generation unavailable; check provider configuration") from e
    res["clips"] = [_hit(c) for c in res["clips"]]
    return res


@app.get("/api/answers")
def answers(limit: int = Query(50, ge=1, le=100), owner=Depends(user)) -> list[dict]:
    p = DATA / "answers" / "history.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()][-limit:][::-1]
    for r in rows:
        r["clips"] = [_hit(c) for c in r["clips"]]
    return rows


@app.get("/api/experiments")
def experiments(transcripts: str | None = Query(None, pattern="^[a-zA-Z0-9_-]+$"), owner=Depends(user)) -> dict:
    """Latest results, or the run over a specific transcript engine (?transcripts=whisper|gemma)."""
    p = EXPERIMENTS_DIR / (f"results.{transcripts}.json" if transcripts else "results.json")
    if not p.exists():
        raise HTTPException(404, "No experiment results for this corpus. Sample mode has labeled UI fixtures.")
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

from .mentor_api import router as mentor_router
app.include_router(mentor_router)
from .demo import router as demo_router
app.include_router(demo_router)

request_slots = asyncio.Semaphore(16)

@app.middleware('http')
async def bounded_body(request: Request, call_next):
    if request.url.path == '/api/health':
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response
    if request_slots.locked():
        return JSONResponse(status_code=429, content={'detail':'server concurrency limit'})
    async with request_slots:
        if request.url.path.startswith('/media/'):
            try:
                user(request)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code,content={'detail':exc.detail})
        if request.method in ('POST', 'PUT', 'PATCH') and request.url.path != '/api/ingest':
            size = 0
            chunks = []
            try:
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > 3 * 1024 * 1024:
                            return JSONResponse(status_code=413, content={'detail':'request exceeds 3 MiB'})
                        chunks.append(chunk)
            except TimeoutError:
                return JSONResponse(status_code=408, content={'detail':'request upload timed out'})
            request._body = b''.join(chunks)
        response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'private, max-age=60'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response

@app.get('/api/openapi.json', include_in_schema=False)
def api_schema():
    return app.openapi()

from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def safe_request_validation(request: Request, exc: RequestValidationError):
    # Default Pydantic errors echo input values (including oversized images,
    # speech/task text or accidentally pasted credentials). Never return them.
    fields = {'body','query','path','header','yaml','expected_version','version',
              'consent','camera_id','frame_id','captured_at','image','feature',
              'config_version','request_id','audio','duration_ms','goal','step',
              'completed','question','view','dim','k','use_video','use_audio',
              'q','video_id','file','limit','transcripts','pid','sid'}
    errors = [{'loc':[part if isinstance(part,int) or part in fields else '<field>' for part in error.get('loc',[])],
               'msg':'Invalid request field', 'type':error.get('type','invalid')}
              for error in exc.errors()[:16]]
    return JSONResponse(status_code=422, content={'detail':errors})

from .jobs import router as jobs_router
app.include_router(jobs_router)

from .conversation import router as conversation_router
from .research_jobs import router as research_router
app.include_router(conversation_router)
app.include_router(research_router)
