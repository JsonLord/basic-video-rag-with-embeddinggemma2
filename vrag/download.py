"""Fetch the latest N uploads from a YouTube channel: 480p mp4, creator captions, thumbnail, slim metadata."""

import json
import subprocess
import sys

from rich.console import Console

from .config import CHANNEL_URL, NUM_VIDEOS, VIDEOS_DIR

console = Console()

# 480p is plenty for 1fps frame embeddings and for the generator, and keeps disk use ~20MB per 10 min.
FORMAT = "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]"
META_KEYS = [
    "id", "title", "description", "duration", "upload_date", "view_count", "like_count",
    "comment_count", "tags", "categories", "chapters", "channel", "webpage_url",
]


def ytdlp(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "yt_dlp", *args], capture_output=True, text=True)


def list_latest(n: int = NUM_VIDEOS, channel: str = CHANNEL_URL) -> list[str]:
    # Over-fetch then drop Shorts / live streams that have no duration.
    out = ytdlp("--flat-playlist", "--playlist-end", str(n * 2), "--print", "%(id)s|%(duration)s", channel)
    ids = []
    for line in out.stdout.splitlines():
        vid, _, dur = line.partition("|")
        if dur not in ("NA", "") and float(dur) >= 120:
            ids.append(vid)
    return ids[:n]


def download(video_id: str) -> None:
    vdir = VIDEOS_DIR / video_id
    vdir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    if not (vdir / "video.mp4").exists():
        r = ytdlp("-f", FORMAT, "--merge-output-format", "mp4", "--write-info-json",
                  "--write-thumbnail", "--convert-thumbnails", "jpg",
                  "-o", str(vdir / "video.%(ext)s"), url)
        if r.returncode != 0:
            raise RuntimeError(f"yt-dlp failed for {video_id}: {r.stderr[-500:]}")
    if not list(vdir.glob("captions*.vtt")):
        # Creator-uploaded captions only (much cleaner than auto-captions). Requesting a single
        # language with a sleep avoids the HTTP 429s that multi-language subtitle requests trigger.
        ytdlp("--skip-download", "--write-subs", "--sub-langs", "en-US,en-GB,en",
              "--sub-format", "vtt", "--sleep-subtitles", "3",
              "-o", str(vdir / "captions.%(ext)s"), url)
    info_path = vdir / "video.info.json"
    if info_path.exists():
        # The raw info.json is ~10MB of format tables; keep only what the app shows.
        info = json.loads(info_path.read_text())
        meta = {k: info.get(k) for k in META_KEYS}
        (vdir / "meta.json").write_text(json.dumps(meta, indent=2))
        info_path.unlink()


def run(n: int = NUM_VIDEOS) -> list[str]:
    ids = list_latest(n)
    console.print(f"[bold]Downloading {len(ids)} videos[/bold] from {CHANNEL_URL}")
    for i, vid in enumerate(ids, 1):
        download(vid)
        caps = list((VIDEOS_DIR / vid).glob("captions*.vtt"))
        title = json.loads((VIDEOS_DIR / vid / "meta.json").read_text())["title"]
        console.print(f"  [{i}/{len(ids)}] {vid}  {title}  captions={'yes' if caps else '[red]no[/red]'}")
    return ids
