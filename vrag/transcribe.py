"""Timestamped transcripts -> data/videos/<id>/transcript.<engine>.json as [{start, end, text}, ...].

Engines:
  gemma   - Gemma 4 12B on the vLLM server (default). Audio is cut at pauses into <=28s chunks,
            because Gemma 4 only hears the first 30s of any audio input.
  whisper - Whisper large-v3-turbo locally, with word timestamps.
Creator captions (captions*.vtt from the YouTube download path) win over both when present.

transcript.json is a copy of the *active* engine's transcript; everything downstream reads that.
"""

import io
import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from rich.console import Console

from .config import ASR_ENGINE, GEN_MODEL, VIDEOS_DIR

console = Console()

ENGINE_MODELS = {"whisper": "openai/whisper-large-v3-turbo", "gemma": "google/gemma-4-12B-it (vLLM)"}
SR = 16000
_asr = None


def _parse_vtt(path: Path) -> list[dict]:
    import webvtt

    return [
        {"start": round(c.start_in_seconds, 2), "end": round(c.end_in_seconds, 2), "text": " ".join(c.text.split())}
        for c in webvtt.read(str(path))
        if c.text.strip()
    ]


def load_audio(path: Path, sr: int = SR) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True,
    )
    return np.frombuffer(out.stdout, dtype=np.float32)


# ---------------------------------------------------------------- whisper

def _whisper(path: Path) -> list[dict]:
    global _asr
    import torch
    from transformers import pipeline

    if _asr is None:
        _asr = pipeline("automatic-speech-recognition", model=ENGINE_MODELS["whisper"], dtype=torch.bfloat16, device="cuda")
    audio = load_audio(path)
    # Word-level timestamps: chunk-level ones from the batched pipeline often collapse into
    # multi-minute cues, which breaks segmentation. Words are regrouped into cues below.
    out = _asr(
        {"raw": audio, "sampling_rate": SR},
        return_timestamps="word",
        chunk_length_s=30,
        batch_size=4,  # word timestamps need eager cross-attention maps, which are memory-hungry
        generate_kwargs={"language": "en", "task": "transcribe"},
    )
    return _group_words(out["chunks"])


def _group_words(words: list[dict], max_s: float = 8.0) -> list[dict]:
    """Group word timestamps into caption-like cues: break after sentence punctuation or every ~max_s."""
    cues, cur = [], []
    for w in words:
        start, end = w["timestamp"]
        if start is None:
            continue
        end = end if end is not None else start + 0.3
        # Whisper word tokens carry their own leading space ("1" + ".6"), so join raw text.
        cur.append((start, end, w["text"]))
        if w["text"].rstrip().endswith((".", "?", "!")) or end - cur[0][0] >= max_s:
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    return [
        {"start": round(c[0][0], 2), "end": round(c[-1][1], 2), "text": "".join(t for _, _, t in c).strip()}
        for c in cues
    ]


# ---------------------------------------------------------------- gemma

GEMMA_PROMPT = (
    "Transcribe the following audio verbatim in English. Output only the transcript text, with normal "
    "punctuation and capitalisation. Do not summarise, translate, or add commentary. If there is no speech, output nothing."
)
CHUNK_MIN_S, CHUNK_MAX_S = 18.0, 28.0  # Gemma 4 truncates audio inputs at 30s
# Every chunk is padded with silence to exactly this length. vLLM 0.23's Gemma 4 audio encoder
# crashes the whole engine ("'list' object has no attribute 'squeeze'") when clips of different
# lengths land in one encoder batch; identical lengths keep the features stackable.
PAD_S = 30.0


def split_at_pauses(audio: np.ndarray, sr: int = SR) -> list[tuple[int, int]]:
    """Chunks of CHUNK_MIN_S..CHUNK_MAX_S, each ending at the quietest 50ms frame in that window,
    so cuts land in pauses between words rather than mid-word."""
    hop = sr // 20
    n_frames = len(audio) // hop
    rms = np.sqrt(np.mean(audio[: n_frames * hop].reshape(n_frames, hop) ** 2, axis=1) + 1e-12)
    # Smooth over ~250ms so a single quiet frame inside a word doesn't count as a pause.
    rms = np.convolve(rms, np.ones(5) / 5, mode="same")
    chunks, start = [], 0
    while start < len(audio):
        if len(audio) - start <= CHUNK_MAX_S * sr:
            chunks.append((start, len(audio)))
            break
        lo = start // hop + int(CHUNK_MIN_S * 20)
        hi = start // hop + int(CHUNK_MAX_S * 20)
        cut = (lo + int(np.argmin(rms[lo:hi]))) * hop
        chunks.append((start, cut))
        start = cut
    return chunks


def _wav_b64(samples: np.ndarray) -> str:
    import base64

    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, samples, SR, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def pad_audio(samples: np.ndarray, seconds: float = PAD_S) -> np.ndarray:
    n = int(seconds * SR)
    samples = samples[:n]
    return np.pad(samples, (0, n - len(samples))) if len(samples) < n else samples


# A word or short phrase repeated 6+ times in a row ("thought thought thought ..."): a decoding loop.
_LOOP = re.compile(r"\b((?:\w+\W+){1,3}?)(?:\1){5,}", re.IGNORECASE)
# Attempts per chunk: greedy first, then a repetition penalty with a little sampling to break loops.
ATTEMPTS = [{"temperature": 0.0}, {"temperature": 0.3, "extra_body": {"repetition_penalty": 1.15}},
            {"temperature": 0.6, "extra_body": {"repetition_penalty": 1.3}}]


def _is_loop(text: str) -> bool:
    return bool(_LOOP.search(text + " "))


def _gemma_chunk(samples: np.ndarray) -> str:
    from .rag import client

    samples = pad_audio(samples)
    audio_b64 = _wav_b64(samples)
    text = ""
    for opts in ATTEMPTS:
        resp = client().chat.completions.create(
            model=GEN_MODEL,
            # ~30s of speech is <=150 tokens; a tight cap stops a runaway loop from eating 1k tokens.
            max_tokens=400,
            # Instruction before the audio: with audio first, Gemma tends to *reply* to the speaker.
            messages=[{"role": "user", "content": [
                {"type": "text", "text": GEMMA_PROMPT},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
            ]}],
            **opts,
        )
        text = " ".join((resp.choices[0].message.content or "").split())
        if not _is_loop(text):
            return text
    # Still looping after retries: keep the transcript but collapse the repeated run to one copy.
    return _LOOP.sub(lambda m: m.group(1), text + " ").strip()


_SENT = re.compile(r"(?<=[.!?])\s+")


def _chunk_cues(text: str, t0: float, t1: float) -> list[dict]:
    """Gemma returns plain text, so sentence times are interpolated by character offset within the chunk.
    Good to a second or two, which is plenty for ~30s retrieval segments."""
    sents = [s for s in _SENT.split(text) if s.strip()]
    total = sum(len(s) for s in sents) or 1
    cues, pos = [], 0
    for s in sents:
        a = t0 + (t1 - t0) * pos / total
        pos += len(s)
        b = t0 + (t1 - t0) * pos / total
        cues.append({"start": round(a, 2), "end": round(b, 2), "text": s.strip()})
    return cues


def _gemma(path: Path, workers: int = 16) -> list[dict]:
    audio = load_audio(path)
    spans = split_at_pauses(audio)
    with ThreadPoolExecutor(workers) as pool:
        texts = list(pool.map(lambda sp: _gemma_chunk(audio[sp[0]:sp[1]]), spans))
    cues = []
    for (a, b), text in zip(spans, texts):
        cues += _chunk_cues(text, a / SR, b / SR)
    return cues


# ---------------------------------------------------------------- orchestration

def transcript_path(vdir: Path, engine: str) -> Path:
    return vdir / f"transcript.{engine}.json"


def ensure_transcript(vdir: Path, engine: str = ASR_ENGINE, force: bool = False, activate: bool = True) -> list[dict]:
    vtts = sorted(vdir.glob("captions*.vtt"))
    out = transcript_path(vdir, "captions" if vtts else engine)
    if force or not out.exists():
        t0 = time.time()
        if vtts:
            cues = _parse_vtt(vtts[0])
        elif engine == "gemma":
            cues = _gemma(vdir / "video.mp4")
        elif engine == "whisper":
            cues = _whisper(vdir / "video.mp4")
        else:
            raise ValueError(f"unknown ASR engine {engine!r}")
        out.write_text(json.dumps(cues, indent=1))
        meta = json.loads((vdir / "meta.json").read_text())
        meta.setdefault("transcribe_seconds", {})[out.stem.split(".")[-1]] = round(time.time() - t0, 1)
        (vdir / "meta.json").write_text(json.dumps(meta, indent=2))
    if activate:
        shutil.copyfile(out, vdir / "transcript.json")
        meta = json.loads((vdir / "meta.json").read_text())
        meta["transcript_source"] = "captions" if vtts else ENGINE_MODELS[engine]
        meta["transcript_engine"] = "captions" if vtts else engine
        (vdir / "meta.json").write_text(json.dumps(meta, indent=2))
    return json.loads(out.read_text())


def available(vdir: Path) -> dict[str, Path]:
    return {p.stem.split(".", 1)[1]: p for p in sorted(vdir.glob("transcript.*.json"))}


def compare(engines: tuple[str, str] = ("whisper", "gemma")) -> list[dict]:
    """Word error rate of one engine's transcript against the other, per video (no ground truth here,
    so this is agreement, not accuracy)."""
    import jiwer

    norm = lambda cues: re.sub(r"[^a-z0-9' ]+", " ", " ".join(c["text"] for c in cues).lower())
    rows = []
    for vdir in sorted(p for p in VIDEOS_DIR.iterdir() if (p / "meta.json").exists()):
        paths = available(vdir)
        if not all(e in paths for e in engines):
            continue
        ref, hyp = (norm(json.loads(paths[e].read_text())) for e in engines)
        out = jiwer.process_words(ref, hyp)
        meta = json.loads((vdir / "meta.json").read_text())
        rows.append({
            "video_id": vdir.name,
            "title": meta["title"],
            "wer": round(out.wer, 4),
            "words": {engines[0]: len(ref.split()), engines[1]: len(hyp.split())},
            "seconds": meta.get("transcribe_seconds", {}),
        })
    return rows


def run(engine: str = ASR_ENGINE, force: bool = False) -> None:
    console.print(f"[bold]Transcribing with {engine}[/bold] ({ENGINE_MODELS[engine]})")
    for vdir in sorted(p for p in VIDEOS_DIR.iterdir() if (p / "video.mp4").exists()):
        t0 = time.time()
        cues = ensure_transcript(vdir, engine=engine, force=force)
        words = sum(len(c["text"].split()) for c in cues)
        console.print(f"  {vdir.name}: {len(cues)} cues, {words} words ({time.time() - t0:.0f}s)")
