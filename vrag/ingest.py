"""Ingest local video files (e.g. the creator's own exports) into data/videos/<id>/.

Each file is matched to its YouTube upload by duration (exports and uploads agree to within a
second or two), which recovers the real title / video ID / view count without downloading
anything. Unmatched files still ingest, keyed by a slug of the filename.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from .config import CHANNEL_URL, DATA, ROOT, VIDEOS_DIR

console = Console()

SOURCE_DIR = ROOT / "sams-videos"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
CHANNEL_CACHE = DATA / "channel.json"
# YouTube reports the duration rounded *up* to whole seconds, so an export of 808.91s lists as 809.
# Accept uploads whose listed duration is 0-1.2s above the file's; nearest-duration matching with a
# symmetric tolerance produced false matches between videos only a second or two apart.
MATCH_WINDOW_S = (-0.3, 1.2)


def channel_listing(refresh: bool = False, limit: int = 60) -> list[dict]:
    """Flat channel listing (id/title/duration/views). Uses the playlist endpoint, which still
    works when per-video pages are bot-blocked. Cached to data/channel.json."""
    if CHANNEL_CACHE.exists() and not refresh:
        return json.loads(CHANNEL_CACHE.read_text())
    out = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--playlist-end", str(limit), "--dump-json", CHANNEL_URL],
        capture_output=True, text=True,
    )
    rows = []
    for line in out.stdout.splitlines():
        d = json.loads(line)
        thumbs = d.get("thumbnails") or []
        rows.append({
            "id": d["id"],
            "title": d.get("title"),
            "duration": d.get("duration"),
            "view_count": d.get("view_count"),
            "channel_position": d.get("playlist_index"),
            "thumbnail_url": thumbs[-1]["url"] if thumbs else None,
            "webpage_url": f"https://www.youtube.com/watch?v={d['id']}",
        })
    if rows:
        CHANNEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CHANNEL_CACHE.write_text(json.dumps(rows, indent=2))
    return rows


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def match_upload(duration: float, listing: list[dict], taken: set[str]) -> dict | None:
    lo, hi = MATCH_WINDOW_S
    cands = [r for r in listing if r.get("duration") and r["id"] not in taken and lo <= r["duration"] - duration <= hi]
    return min(cands, key=lambda r: abs(r["duration"] - duration - 0.5), default=None)


def clean_title(stem: str) -> str:
    """Readable fallback title for files without a matching upload: drop export suffixes."""
    t = re.sub(r"(_processed|\(\d+\)|^final\s*-?\s*)", " ", stem, flags=re.I)
    t = re.sub(r"[_-]+", " ", t)
    return " ".join(t.split()).strip().capitalize() if t.islower() else " ".join(t.split()).strip()


def transcode(src: Path, dst: Path) -> None:
    """480p H.264 proxy with faststart so the browser can seek it. Frame embeddings sample at 1fps,
    so the source's 60fps / 1080p only costs disk and decode time."""
    tmp = dst.with_suffix(".tmp.mp4")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src),
         "-vf", "scale=-2:480", "-r", "30",
         "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "28",
         "-c:a", "aac", "-b:a", "96k", "-ac", "1",
         "-movflags", "+faststart", str(tmp)],
        check=True,
    )
    tmp.rename(dst)


def ingest_file(src: Path, listing: list[dict], taken: set[str]) -> str:
    duration = probe_duration(src)
    upload = match_upload(duration, listing, taken)
    vid = upload["id"] if upload else slugify(src.stem)
    vdir = VIDEOS_DIR / vid
    vdir.mkdir(parents=True, exist_ok=True)

    if not (vdir / "video.mp4").exists():
        transcode(src, vdir / "video.mp4")
    if not (vdir / "thumb.jpg").exists():
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-ss", str(min(30.0, duration / 10)), "-i", str(vdir / "video.mp4"),
             "-frames:v", "1", "-q:v", "3", str(vdir / "thumb.jpg")],
            check=True,
        )

    meta = {
        "id": vid,
        "title": upload["title"] if upload else clean_title(src.stem),
        "duration": round(duration, 2),
        "source_file": src.name,
        "youtube_id": upload["id"] if upload else None,
        "webpage_url": upload["webpage_url"] if upload else None,
        "view_count": upload.get("view_count") if upload else None,
        "channel_position": upload.get("channel_position") if upload else None,
    }
    meta_path = vdir / "meta.json"
    if meta_path.exists():
        meta = {**json.loads(meta_path.read_text()), **meta}
    meta_path.write_text(json.dumps(meta, indent=2))
    return vid


def run(source_dir: Path = SOURCE_DIR) -> list[str]:
    listing = channel_listing()
    files = sorted(p for p in source_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    console.print(f"[bold]Ingesting {len(files)} files[/bold] from {source_dir} ({len(listing)} channel uploads to match)")
    ids: list[str] = []
    for i, f in enumerate(files, 1):
        vid = ingest_file(f, listing, set(ids))
        meta = json.loads((VIDEOS_DIR / vid / "meta.json").read_text())
        tag = "[green]matched[/green]" if meta["youtube_id"] else "[yellow]unmatched[/yellow]"
        console.print(f"  [{i}/{len(files)}] {f.name} -> {vid}  {tag}  {meta['title']}")
        ids.append(vid)
    return ids
