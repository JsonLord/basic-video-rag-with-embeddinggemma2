---
title: Visual Mentor
sdk: docker
app_port: 7860
---

# Visual Mentor

CPU-only remote inference deployment: see [Hugging Face guide](docs/deployment-hf.md). Original offline Video RAG workflow is retained below; install `uv sync --extra offline --extra legacy-local` only on a separate GPU development machine. Never install `serve/` in the CPU Space.

# Video RAG with EmbeddingGemma 2 + Gemma 4 12B

▶️ **Video walkthrough:** https://youtu.be/Q8T9lvtGFNw

Multimodal RAG over the latest uploads on the channel. Every ~30s segment is embedded by
[EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2) five different ways into one
shared 768d space, and Gemma 4 12B (QAT, on vLLM) answers questions by *watching* the retrieved
clips. A Next.js site shows the library, search, RAG answers, and the Matryoshka (MRL) experiments.

```
sams-videos/*.mp4 ─ ingest ─▶ 480p proxy + YouTube match ─ transcribe ─▶ word-timed transcript
                                                                         │
                         segment (~30s, snapped to sentences) ◀──────────┘
                           │  clip.mp4 · audio.wav · keyframe.jpg
                           ▼
            EmbeddingGemma 2 ─▶ text | frame | video | audio | fused   (768d, unit-norm)
                           │
     query ─ SearchQuery ──┤  cosine @ 768/512/256/128 (truncate + renormalise)
                           ▼
         top-k segments ─▶ Gemma 4 12B (transcript + video frames [+ audio]) ─▶ cited answer
```

## Embedding views

| view | what is embedded | why |
|---|---|---|
| `text` | `title: {video title} \| text: {transcript}` | the classic text-RAG baseline |
| `frame` | one keyframe from the middle of the segment | cheapest visual signal |
| `video` | the clip's frames at 1fps (no audio, no text) | what's on screen over time |
| `audio` | raw 16kHz mono audio (no transcript) | can it replace ASR? |
| `fused` | transcript + `<\|video\|>` + `<\|audio\|>` interleaved in one input | all signals in a single vector |
| `hybrid` | reciprocal rank fusion of `text`, `video`, `audio` rankings | multi-vector alternative to `fused` |

Segments target 30s: about 30 frames × 140 tokens + 750 audio tokens + the transcript, which fits
inside the model's 8,192-token window.

## First results (15 videos, 427 segments, 228 synthetic queries)

recall@5 (exact source segment in top 5):

| view | spoken 768d | visual 768d | all 768d | all 256d | all 128d |
|---|---|---|---|---|---|
| text | **0.98** | 0.67 | **0.82** | **0.80** | 0.71 |
| frame | 0.39 | 0.60 | 0.49 | 0.46 | 0.41 |
| video | 0.53 | 0.75 | 0.64 | 0.59 | 0.52 |
| audio | 0.82 | 0.61 | 0.71 | 0.66 | 0.57 |
| fused | 0.84 | **0.78** | 0.81 | 0.77 | 0.69 |
| hybrid | 0.84 | 0.69 | 0.77 | 0.74 | **0.72** |

- **Spoken queries favour transcripts.** Text is near-perfect. Raw audio with no ASR reaches 0.82.
  The spoken queries were written from transcripts, which biases the comparison toward the text view.
- **Visual queries favour pixels.** Fused (0.78) and video (0.75) beat text (0.67). This is where multimodal embedding pays off.
- **MRL:** 256d keeps about 95% of 768d quality across views. 128d costs 10 to 15 points, except hybrid,
  where rank fusion absorbs most of the loss.
- Caveats: the queries are synthetic, Gemma 4 always produced a "visual" query even for talking-head shots,
  and some spoken queries are vague. Add real queries to `data/eval/manual.jsonl` and re-run `vrag experiments`.

## Setup

Two separate uv environments, so vLLM's pinned torch/transformers don't clash with the embedding stack:

```bash
uv sync --extra offline --extra legacy-local  # GPU-only offline pipeline; not the CPU Space
(cd serve && uv sync)       # vLLM 0.23.0 for Gemma 4 12B QAT
(cd web && npm install)     # Next.js site
```

## Build the index

Put video files in `sams-videos/`, then:

```bash
serve/serve.sh --bg --mtp   # Gemma 4 12B QAT on :8001 (needed for evalset + ask)
uv run vrag build           # ingest -> transcribe -> segment -> embed
uv run vrag evalset         # Gemma 4 watches sampled segments, writes spoken + visual queries
uv run vrag experiments     # view x MRL-dim retrieval grid -> data/experiments/results.json
```

- **ingest** transcodes each file to a 480p proxy and matches it to its YouTube upload by duration
  (YouTube lists durations rounded up), recovering title, ID, and view count with no per-video requests.
- **transcribe** uses Gemma 4 12B on the vLLM server by default (`VRAG_ASR=whisper` switches to Whisper
  large-v3-turbo). Audio is cut at pauses into chunks of 28 seconds or less and padded to exactly 30 seconds.
  Gemma only hears the first 30 seconds of any clip, and vLLM 0.23 crashes when it batches clips of different lengths.
  Sentence times are interpolated within each chunk. Chunks that fall into a repetition loop are retried with a
  repetition penalty. On this corpus it took about 100 seconds for 3.9 hours of audio (Whisper: about 35 minutes),
  with 4.3% word disagreement between the two. `uv run vrag switch-transcripts gemma|whisper` swaps the transcripts
  behind the text and fused views while keeping the segment boundaries fixed.
- `uv run vrag download` is an alternative that pulls straight from YouTube, but YouTube often bot-blocks it.

## Run the app

```bash
scripts/dev.sh              # vLLM (if not running) + FastAPI :8000 + Next.js :3000
```

or each separately: `uv run vrag api`, `cd web && npm run dev`. To open the dev site from other
machines, list their hostnames/IPs in `web/.env.local` as `VRAG_DEV_ORIGINS=host1,host2,*.your-tailnet.ts.net`.
CLI question answering:
`uv run vrag ask "what did Sam say about 1.6-bit DeepSeek?"`.

## Gotchas found along the way

- EmbeddingGemma 2 must run in **bf16 or fp32**. fp16 silently produces NaN or degraded vectors.
- After MRL truncation, vectors **must be re-normalised** (`vrag/index.py:truncate`).
- Video input in sentence-transformers needs `torchcodec`, because torchvision removed `read_video`.
- vLLM needs `vllm[audio]`, otherwise audio inputs return "Invalid or unsupported audio file".
- Gemma 4 treats audio placed before the instruction as a conversation turn. Put the instruction first.
- Whisper's batched *chunk* timestamps can collapse into 5-minute cues. Word timestamps fix that, but Whisper
  still invents or duplicates text where its 30-second windows meet, for example "I'll see you next time" mid-video.
- Gemma 4 occasionally gets stuck in a loop ("thought thought thought…"). These are detected and retried.
- `serve/serve.sh` carries over the Blackwell/VPN workarounds from `~/projects/gemma-4-qat`.

## Layout

```
vrag/            pipeline + API (python)
  ingest.py      local files -> data/videos/<id>/{video.mp4, thumb.jpg, meta.json}
  transcribe.py  transcript.json
  segment.py     segments.json + segments/NNN.{mp4,wav,jpg}
  embedder.py    EmbeddingGemma 2 wrapper, per-view inputs
  embed.py       data/index/<view>.npy + manifest.json
  index.py       cosine search, MRL truncation, hybrid RRF
  rag.py         retrieval + Gemma 4 generation (video_url / audio_url clips)
  evalset.py     synthetic spoken/visual queries (+ data/eval/manual.jsonl for your own)
  experiments.py metrics grid
  api.py         FastAPI for the site
serve/           vLLM env + serve/stop scripts
web/             Next.js 16 site (Library, Search, Ask, Experiments)
```
