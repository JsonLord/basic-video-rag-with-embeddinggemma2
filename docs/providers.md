# Provider protocols and routing

All inference is remote. Providers declare capabilities, an HTTPS endpoint **environment-variable name**, a model ID, and an optional credential **environment-variable reference**. Credentials never belong in YAML. `VM_ALLOWED_HOSTS` is an administrator-controlled, exact hostname allowlist; uploaded YAML cannot change it. Base URLs include any API prefix, for example `/v1`; adapters append paths below. Each actual call repeats destination/trust checks, including fallbacks. Redirects are rejected.

| Adapter | Wire contract | Supported outputs |
| --- | --- | --- |
| `openai-chat-vision` | POST `/chat/completions`, text/image_url content parts, bounded `max_tokens`; `choices[0].message.content` | semantic descriptions, reasoning, advisory decisions; never boxes |
| `openai-embeddings` | POST `/embeddings`, model/input; `data[0].embedding` | finite nonzero text vectors only |
| `openai-transcription` | multipart POST `/audio/transcriptions`, file/model; `text` | transcription of bounded browser WebM clips |
| `detection-http` | POST `/detect` using the gateway contract below | validated normalized boxes; persistent IDs only if object_tracking is explicitly declared |
| `laya-vision` | POST `/v1/system-one`, object state/questions and bare `imageBase64`; source and captured-live response forms | bounded `noul` image-inspectability score mapped to an advisory decision; no boxes or generated prose |

All adapters are mock-contract tested. The release review additionally verified a synthetic image against the live Laya gateway; NVIDIA, VLM, embedding and Whisper remain mock-only. See release-readiness.md for exact evidence. OpenAI compatibility alone does not imply image, audio, video, tracking or embedding support. Verify the exact model and protocol before declaring capabilities. Laya can use the OpenAI adapter only if its official documentation establishes that protocol; do not simply rename an arbitrary endpoint.

## Detection gateway

NVIDIA products do not share a universal detection API. This adapter expects an external, authenticated gateway you control which translates its actual NVIDIA-compatible service into:

```json
{"model":"detector-id","image":"data:image/jpeg;base64,...","frame_id":1,"camera_id":"camera2"}
```

Response:

```json
{"frame_id":1,"camera_id":"camera2","width":640,"height":480,"detections":[{"label":"hand","bbox_xyxy":[0.2,0.1,0.6,0.8],"confidence":0.9}]}
```

Dimensions must equal the submitted image. `bbox_xyxy` is normalized to the unmirrored image; x1<x2 and y1<y2, all within [0,1]. The backend supplies per-frame detection IDs and provider provenance. A real tracker may supply `object_id` only when its capability is verified. The browser draws on the exact analyzed still, using its original aspect ratio; mirror applies to both image and overlay. Moving preview frames never receive stale detections.

## Strategies

`single` requires one provider. `fallback` tries another only for configured timeout/provider_error/invalid_output categories; permission, capability, circuit or credential errors stop it. `parallel` runs bounded independent calls and supports all, first_valid (cancels remaining work), and quorum (rejects incomplete quorum). `sequential` passes typed prior observations as untrusted data and stops on failure. `conditional` uses only validated camera_id/has_detections equality predicates, never executable expressions.

Fusion preserves detector boxes and semantic decisions in separate typed lists, preserving source and disagreement. It does not average text, infer boxes, associate unrelated object identities, or claim a persistent tracker. Semaphore concurrency, input/response limits, timeout, cancellation and a three-failure/30-second circuit breaker bound work. Each configuration request gets a deep snapshot and version. Session frames additionally enforce 2 FPS and one in-flight call per camera. Disconnected frame/audio/guidance requests cancel downstream tasks.

## Embedding migration

Keep legacy data. Configure `rag.text_embeddings` with one verified remote text embedding provider. From the repository root:

```bash
VM_STATE_DIR=/path/to/config-state python scripts/reindex-remote.py --source data/index --output data/indexes/model-v1
```

Only run after explicit approval to send those transcripts to the configured destination. Set `VRAG_INDEX_DIR` to the new directory and restart the API. Model **and endpoint** identity plus dimensions are checked before query. Changing either requires a separate index. Text-only providers create only text vectors; image/video/audio/fused views are unavailable. MRL truncation is disabled unless explicitly supported in the index manifest. Existing legacy offline scripts still use original local modules; install their extras on a separate suitable GPU machine, never in the Space. Remote RAG sends bounded precomputed segment keyframes, transcripts and source timestamps, never local file URLs; raw audio RAG is explicitly unavailable.

## Verified Laya router contract (release review)

Reference source: [JsonLord/laya-inference at 77b324ac6c72efee883c41fd333e84007c55bed0](https://github.com/JsonLord/laya-inference/tree/77b324ac6c72efee883c41fd333e84007c55bed0). Validation reads `state` (object), `questions` (typed question map), and optional bare `imageBase64`. The top-level JSON key `image` is not that wire protocol. We use JSON and do not rely on the source's inconsistent single-file multipart handling.

The checked-in reference vision service is a placeholder, so it cannot establish real deployed inference. Read-only live `/health`, `/ready` and `/v1/info` checks reported ready, placeholder=false and model thaitea/laya-vision. A generated 64×64 white image returned backend laya-vision, model thaitea/laya-vision and checkpoint revision f2fe3c12cb6d04c59d8a190250bf3fb40fc828dc. The captured response is in tests/fixtures/laya-live-synthetic.json. The remote checkpoint's PyTorch/runtime metadata describes the external service, not packages installed in Visual Mentor.

The source response uses `results.<question>`; the deployed gateway uses `results.answers.<question>` with additional provenance. Only these two evidenced forms are accepted. Wrong backend/model, placeholder markers, missing typed noul answers and non-probability values fail closed. The current adapter asks one fixed noul question, "Is this image clear enough for human visual inspection?", with bounded advisory task context. It reports the probability as a visual_assessment decision, never as a detection, spatial coordinate, autonomous action or free-form scene description. Source choice/score formats are documented by the upstream service but are not exposed as additional product features in this release.

Set LAYA_BASE_URL to `https://leon4gr45-needle-router.hf.space` (gateway root, no `/v1` suffix). Use model `thaitea/laya-vision`, timeout_ms 60000 and concurrency 1. The public live call did not require credentials; add api_key_secret: LAYA_API_KEY only when that endpoint requires it. The adapter always checks the configured expected model; do not relabel another endpoint as Laya.

Use laya-only.yaml or laya-nvidia-hybrid.yaml after destination approval; the older laya-pending template remains a disabled historical default. Hybrid routing keeps Laya decisions and detector boxes separate, preserving provenance. It does not attach semantic scores to a specific object or invent a tracker. The NVIDIA gateway contract is still unverified against a real endpoint.

From the prepared repository, an explicit synthetic-only connection check is:

```bash
LAYA_BASE_URL=https://leon4gr45-needle-router.hf.space \
VM_ALLOWED_HOSTS=leon4gr45-needle-router.hf.space \
/workspace/visual-mentor-venv/bin/python scripts/check-laya.py --synthetic
```

Without --synthetic, this helper reads metadata only. Secrets, when required, must already be supplied securely through the environment. No real camera image is read by this helper. `/openapi.json` and `/docs` are currently 404 on the remote gateway; its deployed source revision remains unknown. Source publication/schema changes are an operator task and were not performed.
