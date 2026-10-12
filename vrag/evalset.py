"""Build a retrieval eval set: Gemma 4 watches sampled segments and writes search queries for them.

Two query types per segment, because they stress different embedding views:
  spoken - what someone would search for to find what Sam *says* here
  visual - something only *shown* on screen (slide text, UI, code, chart), not said aloud
Hand-written queries can be added to data/eval/manual.jsonl as {"query", "segment_id", "type"}.
"""

import json
import random
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import track

from .config import EVAL_DIR, GEN_MODEL, INDEX_DIR
from .rag import client, fmt_ts
from .segment import media_paths

console = Console()

PER_VIDEO = 8

PROMPT = """You are helping build a search benchmark for a video library of AI/ML YouTube videos.
Below is one ~30 second clip: its transcript and its video frames.

Write two search queries that a viewer might type to find THIS specific moment again:
1. "spoken": a query about something specific Sam SAYS in this clip. Paraphrase rather than copying
   phrases verbatim. It must be specific to this clip, not a generic topic of the whole video.
2. "visual": a query about something specific that is SHOWN on screen in the frames but is NOT said
   in the transcript (e.g. text on a slide, a UI or website, a code snippet, a chart, a demo output, a person or object).
   Describe it the way a viewer remembers it ("the slide with the comparison table of ..."). Use null if
   the frames show nothing distinctive beyond a talking head.

Video title (do not repeat it verbatim in the queries): "{title}"
Clip time: {start}-{end}
Transcript: {text}

Return JSON: {{"spoken": "...", "visual": "..." or null, "visual_evidence": "what on screen the visual query refers to"}}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "spoken": {"type": "string"},
        "visual": {"type": ["string", "null"]},
        "visual_evidence": {"type": ["string", "null"]},
    },
    "required": ["spoken", "visual", "visual_evidence"],
}


def sample_segments(segments: list[dict], per_video: int, seed: int = 0) -> list[dict]:
    """Evenly spaced segments per video, skipping the intro and outro which are generic."""
    rng = random.Random(seed)
    by_video: dict[str, list[dict]] = {}
    for s in segments:
        by_video.setdefault(s["video_id"], []).append(s)
    picked = []
    for segs in by_video.values():
        inner = segs[1:-1] or segs
        if len(inner) <= per_video:
            picked += inner
            continue
        step = len(inner) / per_video
        picked += [inner[min(len(inner) - 1, int(i * step + rng.random() * step))] for i in range(per_video)]
    return picked


def gen_queries(seg: dict) -> dict:
    prompt = PROMPT.format(title=seg["title"], start=fmt_ts(seg["start"]), end=fmt_ts(seg["end"]), text=seg["text"])
    resp = client().chat.completions.create(
        model=GEN_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "video_url", "video_url": {"url": f"file://{media_paths(seg)['clip']}"}},
        ]}],
        response_format={"type": "json_schema", "json_schema": {"name": "queries", "schema": SCHEMA}},
        max_tokens=400,
        temperature=0.7,
    )
    return json.loads(resp.choices[0].message.content)


def run(per_video: int = PER_VIDEO, workers: int = 8) -> list[dict]:
    segments = json.loads((INDEX_DIR / "segments.json").read_text())
    picked = sample_segments(segments, per_video)
    console.print(f"[bold]Generating queries[/bold] for {len(picked)} segments with {GEN_MODEL}")
    rows = []
    with ThreadPoolExecutor(workers) as pool:
        for seg, q in track(zip(picked, pool.map(gen_queries, picked)), total=len(picked)):
            rows.append({"query": q["spoken"], "type": "spoken", "segment_id": seg["id"], "video_id": seg["video_id"]})
            if q.get("visual"):
                rows.append({"query": q["visual"], "type": "visual", "segment_id": seg["id"],
                             "video_id": seg["video_id"], "evidence": q.get("visual_evidence")})
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with (EVAL_DIR / "queries.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    console.print(f"  wrote {len(rows)} queries ({sum(r['type'] == 'visual' for r in rows)} visual)")
    return rows


def load() -> list[dict]:
    rows = []
    for name in ("queries.jsonl", "manual.jsonl"):
        p = EVAL_DIR / name
        if p.exists():
            rows += [{**json.loads(line), "source": name.split(".")[0]} for line in p.read_text().splitlines() if line.strip()]
    return rows
