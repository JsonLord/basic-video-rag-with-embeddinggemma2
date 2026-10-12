"""Answer questions over the video corpus: retrieve segments, then let Gemma 4 12B watch them.

Each retrieved segment goes to the generator as its transcript text plus the clip itself (sampled
frames via video_url) and optionally the raw audio, so it can answer from what's on screen, not
just what was said.
"""

import json
import time
from datetime import datetime, timezone

from openai import OpenAI

from .config import DATA, GEN_BASE_URL, GEN_MODEL
from .embedder import encode_query
from .index import get_index
from .segment import media_paths

HISTORY = DATA / "answers" / "history.jsonl"

SYSTEM = """You answer questions about Sam Witteveen's YouTube videos using only the retrieved clips provided.
Each clip is numbered [1], [2], ... and comes with its video title, timestamp range, transcript, and the video frames (and sometimes audio).
Rules:
- Use both what is said (transcript/audio) and what is shown on screen (slides, code, UIs, demos).
- Cite clips inline like [2] after the claims they support. Only cite clips you actually used.
- If the clips don't contain the answer, say so plainly rather than guessing.
- Be concise: a short direct answer first, then supporting detail if useful."""


def fmt_ts(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def client() -> OpenAI:
    return OpenAI(base_url=GEN_BASE_URL, api_key="local")


def build_messages(question: str, hits: list[dict], use_video: bool, use_audio: bool) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": f"Question: {question}\n\nRetrieved clips:"}]
    for n, h in enumerate(hits, 1):
        m = media_paths(h)
        # Repeat the clip number on every part: with several interleaved videos the model otherwise
        # loses track of which [n] a transcript belongs to and cites the wrong clip.
        content.append({"type": "text", "text": (
            f"\n=== Clip [{n}] === Video: \"{h['title']}\" ({fmt_ts(h['start'])}-{fmt_ts(h['end'])})\n"
            f"Clip [{n}] transcript: {h['text']}\n"
            + (f"Clip [{n}] frames:" if use_video else "")
        )})
        if use_video:
            content.append({"type": "video_url", "video_url": {"url": f"file://{m['clip']}"}})
        if use_audio:
            content.append({"type": "text", "text": f"Clip [{n}] audio:"})
            content.append({"type": "audio_url", "audio_url": {"url": f"file://{m['audio']}"}})
        content.append({"type": "text", "text": f"=== End of clip [{n}] ==="})
    content.append({"type": "text", "text": f"\nNow answer the question, citing clips: {question}"})
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]


def answer(question: str, view: str = "fused", dim: int = 768, k: int = 4,
           use_video: bool = True, use_audio: bool = False, max_tokens: int = 1024) -> dict:
    t0 = time.time()
    q = encode_query(question)
    hits = get_index().search(q, view=view, dim=dim, k=k)
    t_retrieve = time.time() - t0

    t1 = time.time()
    resp = client().chat.completions.create(
        model=GEN_MODEL,
        messages=build_messages(question, hits, use_video, use_audio),
        max_tokens=max_tokens,
        temperature=0.2,
    )
    t_generate = time.time() - t1

    result = {
        "question": question,
        "answer": resp.choices[0].message.content,
        "settings": {"view": view, "dim": dim, "k": k, "use_video": use_video, "use_audio": use_audio},
        "clips": [{k_: h[k_] for k_ in ("id", "video_id", "title", "idx", "start", "end", "text", "score")} for h in hits],
        "usage": {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens},
        "timing": {"retrieve_s": round(t_retrieve, 3), "generate_s": round(t_generate, 2)},
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a") as f:
        f.write(json.dumps(result) + "\n")
    return result
