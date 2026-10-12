"""Cut each video into ~30s segments snapped to transcript cue boundaries, and extract the media
each embedding view needs: a 480p clip, 16kHz mono wav, and a middle keyframe."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.console import Console

from .config import INDEX_DIR, SEGMENT_MIN_S, SEGMENT_TARGET_S, VIDEOS_DIR

console = Console()


def plan_segments(cues: list[dict], duration: float) -> list[dict]:
    """Greedily pack cues into windows of ~SEGMENT_TARGET_S, so no sentence is cut mid-way."""
    segs, cur = [], []
    for cue in cues:
        cur.append(cue)
        if cue["end"] - cur[0]["start"] >= SEGMENT_TARGET_S:
            segs.append(cur)
            cur = []
    if cur:
        # Fold a short tail into the previous segment rather than indexing a 5s scrap.
        if segs and cur[-1]["end"] - cur[0]["start"] < SEGMENT_MIN_S:
            segs[-1].extend(cur)
        else:
            segs.append(cur)
    out = []
    for i, group in enumerate(segs):
        # Segments tile the video: each starts where the previous ended, so silences are covered too.
        start = 0.0 if i == 0 else out[-1]["end"]
        end = duration if i == len(segs) - 1 else group[-1]["end"]
        out.append({"idx": i, "start": round(start, 2), "end": round(end, 2),
                    "text": " ".join(c["text"] for c in group)})
    return out


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def extract_media(video: Path, seg: dict, out_dir: Path) -> None:
    stem = out_dir / f"{seg['idx']:03d}"
    start, dur = seg["start"], seg["end"] - seg["start"]
    if not stem.with_suffix(".mp4").exists():
        _ffmpeg("-ss", str(start), "-t", str(dur), "-i", str(video),
                "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "30", "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart", str(stem.with_suffix(".mp4")))
    if not stem.with_suffix(".wav").exists():
        _ffmpeg("-ss", str(start), "-t", str(dur), "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                str(stem.with_suffix(".wav")))
    if not stem.with_suffix(".jpg").exists():
        _ffmpeg("-ss", str(start + dur / 2), "-i", str(video), "-frames:v", "1", "-q:v", "3",
                str(stem.with_suffix(".jpg")))


def run() -> list[dict]:
    """Segment every transcribed video and write the corpus manifest data/index/segments.json."""
    corpus = []
    for vdir in sorted(p for p in VIDEOS_DIR.iterdir() if (p / "transcript.json").exists()):
        meta = json.loads((vdir / "meta.json").read_text())
        cues = json.loads((vdir / "transcript.json").read_text())
        segs = plan_segments(cues, meta["duration"])
        seg_dir = vdir / "segments"
        seg_dir.mkdir(exist_ok=True)
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda sg: extract_media(vdir / "video.mp4", sg, seg_dir), segs))
        for seg in segs:
            corpus.append({
                "id": f"{vdir.name}_{seg['idx']:03d}",
                "video_id": vdir.name,
                "title": meta["title"],
                **seg,
            })
        (vdir / "segments.json").write_text(json.dumps(segs, indent=1))
        console.print(f"  {vdir.name}: {len(segs)} segments  ({meta['title']})")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "segments.json").write_text(json.dumps(corpus, indent=1))
    console.print(f"[bold]{len(corpus)} segments[/bold] across {len({s['video_id'] for s in corpus})} videos")
    return corpus


def retext() -> list[dict]:
    """Refill segment text from the (newly) active transcript while keeping segment boundaries fixed.

    Switching ASR engines this way leaves segment IDs, media, and the visual/audio embeddings untouched,
    so the eval set stays valid and transcript engines can be compared on identical segments.
    Each cue goes to the segment containing its midpoint.
    """
    corpus = []
    for vdir in sorted(p for p in VIDEOS_DIR.iterdir() if (p / "segments.json").exists()):
        meta = json.loads((vdir / "meta.json").read_text())
        cues = json.loads((vdir / "transcript.json").read_text())
        segs = json.loads((vdir / "segments.json").read_text())
        for seg in segs:
            seg["text"] = " ".join(c["text"] for c in cues if seg["start"] <= (c["start"] + c["end"]) / 2 < seg["end"])
        (vdir / "segments.json").write_text(json.dumps(segs, indent=1))
        corpus += [{"id": f"{vdir.name}_{sg['idx']:03d}", "video_id": vdir.name, "title": meta["title"], **sg} for sg in segs]
    (INDEX_DIR / "segments.json").write_text(json.dumps(corpus, indent=1))
    console.print(f"Re-texted {len(corpus)} segments from engine '{transcript_engine()}' transcripts")
    return corpus


def transcript_engine() -> str:
    """Which ASR engine the indexed transcripts came from ('gemma', 'whisper', 'captions' or 'mixed')."""
    engines = {json.loads((v / "meta.json").read_text()).get("transcript_engine", "whisper")
               for v in VIDEOS_DIR.iterdir() if (v / "segments.json").exists()}
    return engines.pop() if len(engines) == 1 else "mixed"


def media_paths(seg: dict) -> dict[str, Path]:
    stem = VIDEOS_DIR / seg["video_id"] / "segments" / f"{seg['idx']:03d}"
    return {"clip": stem.with_suffix(".mp4"), "audio": stem.with_suffix(".wav"), "frame": stem.with_suffix(".jpg")}
