# Provider protocols and routing

All inference is remote. Providers declare capabilities, an HTTPS endpoint **environment-variable name**, a model ID, and an optional credential **environment-variable reference**. Credentials never belong in YAML. `VM_ALLOWED_HOSTS` is an administrator-controlled, exact hostname allowlist; uploaded YAML cannot change it. Base URLs include any API prefix, for example `/v1`; adapters append paths below. Each actual call repeats destination/trust checks, including fallbacks. Redirects are rejected.

| Adapter | Wire contract | Supported outputs |
| --- | --- | --- |
| `openai-chat-vision` | POST `/chat/completions`, text/image_url content parts, bounded `max_tokens`; `choices[0].message.content` | semantic descriptions, reasoning, advisory decisions; never boxes |
| `openai-embeddings` | POST `/embeddings`, model/input; `data[0].embedding` | finite nonzero text vectors only |
| `openai-transcription` | multipart POST `/audio/transcriptions`, file/model; `text` | transcription of bounded browser WebM clips |
| `detection-http` | POST `/detect` using the gateway contract below | validated normalized boxes; persistent IDs only if object_tracking is explicitly declared |
| `laya-vision` | **unavailable pending authoritative Laya/Jev API documentation** | no capabilities assumed; calls fail `protocol_unverified` |

These adapters are mock-contract tested. No real Laya, NVIDIA, VLM, embedding or Whisper endpoint was available during implementation. OpenAI compatibility alone does not imply image, audio, video, tracking or embedding support. Verify the exact model and protocol before declaring capabilities. Laya can use the OpenAI adapter only if its official documentation establishes that protocol; do not simply rename an arbitrary endpoint.

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

## Supplied Laya router

The user identified `https://leon4gr45-needle-router.hf.space` with GET `/health`, `/ready`, `/v1/info` and POST `/v1/system-one`. Endpoint names establish where to inspect metadata, but do not establish System-1 JSON/image encoding or response semantics. During this task the platform proxy returned HTTP 403 at CONNECT, before reaching the service; no service authentication/readiness conclusion follows. The environment draft includes this exact allowed hostname, LAYA_BASE_URL, and a LAYA_API_KEY secret requirement (no secret value). Apply settings and securely supply the binding before retrying `/v1/info` and `/openapi.json`. `config/examples/laya-pending.yaml` preserves the supplied endpoint reference with disabled routes and no invented capabilities until the protocol is verified.
