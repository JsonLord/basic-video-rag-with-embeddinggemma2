# Visual Mentor — Private Hugging Face CPU Space

**Status:** Implementation specification (v1)  
**Target repository:** `JsonLord/basic-video-rag-with-embeddinggemma2`  
**Deployment:** Private Hugging Face Docker Space, port `7860`, CPU-only  
**Principle:** Preserve existing Video RAG functionality; add live dual-camera mentoring and configurable remote inference. No AI weights loaded in the Space or laptop.

## 1. Goals and non-goals

### Goals
1. Retain the existing Next.js video library, clip player, search, Ask/RAG, and experiments functionality.
2. Deploy a **single private Docker Space** serving the UI and FastAPI under one HTTPS origin, listening on port 7860.
3. Run on CPU Basic with no CUDA, torch, transformers, sentence-transformers, local vLLM, or local Whisper in the production image. Target idle RSS under 500 MB and peak under 1 GB if feasible; measure and report rather than masking failures.
4. Add a **Live** tab that lets the user's laptop browser select its built-in camera and an attached USB camera, preview both simultaneously when supported, and send explicitly enabled, sampled frames for remote inference. The Space never accesses USB devices directly.
5. Add **Models & Routing** tab for provider configuration, model-to-feature assignment, YAML import/export, safe validation, test calls, and runtime profile switching.
6. Support Laya/Jev as a fast visual decision provider, external object detector/tracker (e.g. NVIDIA-compatible service), remote vision-language models, remote Whisper transcription, and remote embedding APIs. Models are **remote inference only**.
7. Support single, fallback, parallel, sequential, and conditional routing; support typed fusion of detection boxes and semantic descriptions. Never invent spatial detections from textual LLM responses.
8. Preserve private camera data by default: explicit capture start, no automatic recording, approved inference destinations only, no secret exposure.

### Non-goals for v1
- Real-time 30 FPS inference, guaranteed spatial tracking without an actual tracker, local GPU inference, embedded Docker daemon/research workers, automatic installation of NVIDIA models, or full autonomous mentoring/research agents. Provide extension interfaces for later phases.
- Automatic conversion of arbitrary text-only embedding APIs into multimodal embedding models.

## 2. Existing repository constraints and migration

Verified code structure: `web/` Next.js 16; `vrag/api.py` FastAPI; `vrag/rag.py` uses `openai.OpenAI` with local vLLM base URL and nonstandard `video_url` / `audio_url` with `file://` paths; `vrag/embedder.py` forces `SentenceTransformer(..., device="cuda")`; `vrag/index.py` NumPy cosine retrieval over saved `.npy` vectors; `serve/` vLLM stack. `vrag/api.py` eagerly warms embedding model at startup.

Required adaptations:
- Split dependency groups into **runtime**, **offline ingestion/evaluation**, and **legacy local inference**; install runtime only in production.
- Replace eager `get_model()` startup with health-checked remote provider initialization; missing optional providers should degrade specific features, not crash the app.
- Introduce provider adapters with capability negotiation and per-role credentials; use the OpenAI-compatible interface where supported, but account for provider-specific image/video/audio payloads and detection APIs.
- For cloud VLMs lacking video input, extract a bounded number of frames from a retrieved clip and send supported image parts plus transcript and timestamps. Do not send `file://` references to remote providers.
- Preserve existing index and MRL evaluation only for compatible models; new embedding provider/model/dimension means a separate versioned index and re-embedding. For text-only embeddings, index transcripts and frame captions; disable unsupported video/audio/fused embedding views with explicit UI explanations.
- Keep FFmpeg/video ingestion optional and out of the live request path; retain HTTP Range media playback.
- Ensure existing routes and frontend views still function (with graceful no-index empty states).

## 3. Target architecture

```text
Laptop browser (HTTPS; built-in + USB cameras; local preview)
  ├─ Next.js Live, Library, Search, Ask/Mentor, Models & Routing
  ├─ getUserMedia, device enumeration, per-camera frame sampling
  └─ explicit uploads of selected frames/audio
        │ same-origin /api and /media
Private HF Docker Space :7860
  ├─ static Next.js export (preferred if compatible), or slim Next standalone server
  ├─ FastAPI, session manager, config manager, provider registry
  ├─ live observation coordinator, typed fusion, mentor event stream
  ├─ small NumPy index + SQLite (or ephemeral state)
  └─ outbound HTTPS to approved inference providers
       ├─ Laya/Jev visual decisions
       ├─ external NVIDIA-compatible detector/tracker
       ├─ cloud VLM / mentor reasoning
       ├─ Whisper-compatible remote STT
       └─ remote embeddings
```

Do not require public inbound ports besides 7860. Do not run Docker research agents inside the Space; future research worker integration is outbound HTTPS to authenticated job APIs.

## 4. UI requirements

### Navigation
- `Live` (default), `Library`, `Search`, `Ask / Mentor`, `Models & Routing`, optional `Experiments` developer view.
- Preserve current library/search/Ask UX and mobile-responsive layout.

### Live tab (`/live`)
- Enumerate `videoinput` devices **after user permission**; show browser-provided labels. Do not assume IDs or labels are stable across browsers/restarts.
- Two independently selectable cameras; allow one or both, gracefully report OS/browser device contention.
- Per-camera start/stop, device selection, resolution, sample interval, enable/disable sending, pipeline/profile selection; combined-view toggle.
- Local previews should remain fluid even when inference is slow. Defaults: 640x480, 1 analysis frame/sec per enabled camera, bounded JPEG/WebP quality, configurable cap of 2 FPS for MVP. Backpressure: max 1 in-flight analysis per camera; skip rather than queue stale frames.
- Frame IDs, camera IDs, client monotonic timestamps, server receipt timestamps, config version, and request IDs for correlation.
- Display detector bounding boxes with correct coordinate transforms under aspect-fit, mirrored previews, orientation, and resize. Only draw boxes when the result matches the frame/camera and coordinates are validated. Show confidence and model provenance.
- Observation timeline, model status/latency, errors, last updated time, mentor guidance panel, manual Analyze button, pause/resume, clear session.
- Camera tracks stop on tab teardown, stop button, or permission revocation; no automatic recording or background capture.
- Push-to-talk microphone via browser; send bounded audio clips to remote STT, never initialize local Whisper.

### Models & Routing tab (`/models`)
- Provider registry: label, protocol/adapter, endpoint, model ID, capability declarations, timeout, concurrency, authentication **secret reference**, destination trust tier; never return API key values to browser.
- Feature routing matrix: per-camera scene recognition, object detection, object tracking, visual decision, mentor reasoning, video RAG, text embeddings, multimodal embeddings, transcription, future research.
- Strategies: `single`, `fallback`, `parallel`, `sequential`, `conditional`. `ensemble` only when a typed merger exists; `parallel` policies `all`, `first_valid`, `quorum` where valid.
- YAML editor, file upload (`.yaml`, `.yml`), download template, validate, preview diff, apply atomically, export current redacted config, restore prior version, profile switch. Show actionable validation errors.
- Connection test and dry-run routing using safe synthetic payloads; do not send real camera frames during tests without explicit opt-in.
- Live routing monitor with per-model status, latency, error, and provenance; do not expose secrets or sensitive payloads in logs.

## 5. Configuration format

Create `config/schema.py` (Pydantic) and `config/examples/` YAML templates. The following is an **illustrative schema**; adjust names as needed but preserve these semantics and document any changes.

```yaml
version: 1
profile: hybrid-dual-camera
providers:
  laya:
    adapter: laya-vision
    base_url_env: LAYA_BASE_URL
    api_key_secret: LAYA_API_KEY
    model: laya-vision
    capabilities: [image_understanding, visual_decision]
    trust: approved_sensitive
    timeout_ms: 5000
  nvidia:
    adapter: detection-http
    base_url_env: NVIDIA_DETECTION_BASE_URL
    api_key_secret: NVIDIA_DETECTION_API_KEY
    model: detector-model-id
    capabilities: [object_detection, bounding_boxes]
    trust: approved_sensitive
    timeout_ms: 5000
  vlm:
    adapter: openai-chat-vision
    base_url_env: VLM_BASE_URL
    api_key_secret: VLM_API_KEY
    model: vision-model-id
    capabilities: [image_understanding, reasoning]
    trust: approved_sensitive
  embeddings:
    adapter: openai-embeddings
    base_url_env: EMBEDDINGS_BASE_URL
    api_key_secret: EMBEDDINGS_API_KEY
    model: embedding-model-id
    capabilities: [text_embeddings]
    trust: approved_sensitive
  whisper:
    adapter: openai-transcription
    base_url_env: WHISPER_BASE_URL
    api_key_secret: WHISPER_API_KEY
    model: whisper-model-id
    capabilities: [transcription]
    trust: approved_sensitive
features:
  live.camera1.scene:
    strategy: single
    providers: [laya]
  live.camera2.detection:
    strategy: parallel
    providers: [nvidia, laya]
    result_policy: all
    fusion: spatial_semantic
  live.camera2.tracking:
    strategy: single
    providers: [nvidia]
    enabled: false # Enable only after verified tracker support
  live.visual_decision:
    strategy: fallback
    providers: [laya, vlm]
    fallback_on: [timeout, provider_error, invalid_output]
  rag.text_embeddings:
    strategy: single
    providers: [embeddings]
  audio.transcription:
    strategy: single
    providers: [whisper]
cameras:
  camera1: {analysis_fps: 1, width: 640, height: 480}
  camera2: {analysis_fps: 1, width: 640, height: 480}
privacy:
  record_video: false
  upload_only_on_explicit_start: true
  require_approved_destination_for_camera: true
```

**Camera physical device IDs must be browser-local settings**, not trusted server YAML identifiers. YAML provider entries refer to logical camera slots. Allow user-provided provider endpoints only with an admin-controlled allowlist; arbitrary URLs must not be accepted simply because they are in uploaded YAML.

## 6. API contracts (versioned)

Implement typed request/response models and document OpenAPI schemas:
- `GET /api/health` — lightweight health, no provider secrets.
- `GET /api/providers` — redacted provider/capability list.
- `POST /api/providers/{id}/test` — permission-gated, bounded synthetic test.
- `GET /api/config`, `GET /api/config/template`, `POST /api/config/validate`, `POST /api/config/apply`, `POST /api/config/rollback` — admin-authorized; versioned atomic config updates.
- `POST /api/live/sessions`, `DELETE /api/live/sessions/{id}`.
- `POST /api/live/sessions/{id}/frames` — camera_id, frame_id, capture timestamp, bounded image, requested feature/profile; respond with typed observation and per-provider status. Consider SSE for asynchronous updates, but HTTP request/response is acceptable for v1.
- `POST /api/live/sessions/{id}/transcribe` — bounded audio upload to remote Whisper.
- Keep `/api/videos`, `/api/search`, `/api/search/image`, `/api/ask`, `/media/*`, and experiments endpoints backward compatible where feasible.

Standard observation schema:
```json
{
  "session_id": "session-id", "camera_id": "camera2", "frame_id": "184",
  "config_version": 3, "observed_at": "ISO-8601",
  "detections": [{"object_id": "track-1", "label": "hand", "bbox_xyxy": [0.2, 0.1, 0.6, 0.8], "confidence": 0.9, "source": "nvidia"}],
  "decisions": [{"action": "continue_observation", "reason": "hand visible", "source": "laya"}],
  "provider_results": [{"provider": "laya", "status": "ok", "latency_ms": 240}],
  "warnings": []
}
```
Bounding boxes use **normalized [0,1] xyxy** coordinates with explicitly defined source dimensions and validation. `object_id` must only represent persistent identity if a real tracker supplies it; otherwise use per-frame detection IDs.

## 7. Routing engine behavior

- Provider adapters declare request/response formats and capabilities; do not equate OpenAI chat compatibility with detection, embeddings, video, or transcription compatibility.
- `single`: one model; `fallback`: retry only eligible errors and approved destinations; `parallel`: bounded async calls, independent errors; `sequential`: typed intermediate outputs; `conditional`: validated deterministic predicates (not arbitrary Python expressions).
- Result fusion: spatial detector owns boxes, Laya owns semantic/decision output; associate results by frame and object ID only where supported; preserve provenance and disagreement. Do not average unrelated text outputs or hallucinate box coordinates.
- Timeouts, max input size, rate limiting, bounded concurrency, cancellation, retry budgets, and circuit breakers. Do not queue unbounded frames.
- Sensitivity checks are per actual destination **and repeated after fallback**. No silent sensitive-data routing to unknown providers. Laya inference infrastructure may be approved separately from generic `auto` routes.
- Changes to config affect new requests only; in-flight calls use a snapshot/version.

## 8. Security, privacy, persistence

- Private Space; do not assume HF UI privacy alone authorizes config mutation or outbound provider access. Require admin authorization for configuration APIs; secure same-origin endpoints, validate session ownership, and use CSRF protections where applicable.
- Secrets are HF Space Secrets/environment variables, never in YAML or frontend. Export redacted YAML only.
- Parse YAML safely with strict Pydantic schema, max upload size, no aliases that cause resource exhaustion, no arbitrary code, no file paths or shell commands. Protect against SSRF (approved hosts, DNS/IP checks, redirect restrictions, block metadata and private destinations unless explicitly configured by admin).
- HTTPS camera capture, explicit opt-in before remote frame/audio transfer; display active destinations; no recording by default; no raw camera frames in logs.
- HF Space ephemeral filesystem: configuration history and SQLite/indexes require explicit persistent storage or external store. If absent, clearly label profiles/session state as ephemeral and ship read-only defaults. Use atomic writes and backup before switching.
- Limit uploads, media processing time, payload sizes, retention, and access to recordings. Never expose API credentials in logs, browser responses, or stack traces.

## 9. Docker and deployment

- Add `Dockerfile` (multistage) and HF Space README frontmatter (`sdk: docker`, `app_port: 7860`, private visibility configured in HF settings, not via README alone).
- Prefer Next.js static export served by FastAPI if feature-compatible; otherwise use Next standalone plus FastAPI in one container behind a same-origin reverse proxy. Only port 7860 exposed; no new public ports.
- Runtime image must not download models, require CUDA, initialize vLLM, or run transcription locally. No local AI inference fallback unless explicitly introduced in a separate future profile.
- Add `env.example` with names only, a secret provisioning guide, health checks, and deterministic startup.
- Avoid installing the legacy `serve/` vLLM environment. Preserve offline tooling for developers in optional groups.

## 10. Tests and acceptance gates

1. Build and run the production image on CPU-only machine; no `torch`, `transformers`, `sentence_transformers`, `vllm`, CUDA or model downloads in runtime. Record image size, startup time, idle and peak RSS.
2. Browser E2E: grant camera permission, list two cameras where available, show simultaneous previews, independently start/stop and switch devices; simulated cameras for CI, real USB test documented as manual.
3. Browser sends frames only after explicit opt-in; camera tracks stop on teardown; no frame/video stored by default.
4. Mock provider contract tests for Laya, detector, VLM, embeddings, Whisper; capability failures are explicit.
5. YAML upload valid/invalid tests, secret redaction, SSRF blocking, authorization, atomic apply/rollback, config snapshots.
6. Routing tests: single/fallback/parallel/sequential/conditional, mixed success, timeout, cancellation, confidence/provenance, no stale-frame overlay, sensitive fallback denial.
7. Video RAG regression tests: library, media seeking, text search, Ask with frame fallback for unsupported remote video; provider changes force separate indexes and show disabled incompatible views.
8. UI: Models tab can switch Laya-only, NVIDIA-only, and hybrid routes **without redeploying**; live monitor displays which providers handled a frame.
9. Remote STT push-to-talk works without local Whisper.
10. Private HF Space deploy documented and verified where credentials are available; never claim live success from mocked tests.

## 11. Implementation milestones

- **M0 — Baseline:** inspect repo, inventory dependencies/routes, record tests, produce architecture notes. Do not break legacy workflows.
- **M1 — Cloud-only RAG:** split dependencies, remote provider adapters, eliminate eager CUDA startup, preserve library/search/Ask, test index migration.
- **M2 — HF Docker:** one-port deployment, health, secret handling, persistent-state strategy, CPU resource report.
- **M3 — Live dual camera:** browser capture, two streams, sampling, opt-in, observation APIs, overlays and session lifecycle.
- **M4 — Routing Studio:** provider/feature UI, YAML template/upload/validation/apply/rollback, profile switching, telemetry.
- **M5 — Hybrid perception:** Laya decision adapter + NVIDIA-compatible detection adapter + parallel/fallback/typed fusion, remote Whisper.
- **M6 — Mentoring foundation:** observation-to-guidance contract, simple task state, hooks for future remote research agents; do not claim full mentoring autonomy.

## 12. Deliverables

Code, tests, migration notes, `spec.md`, `config/examples/*.yaml`, `env.example`, `Dockerfile`, HF README configuration, documented OpenAPI, `docs/architecture.md`, `docs/deployment-hf.md`, `docs/security.md`, and a validation report with actual vs target metrics. Preserve original features and avoid modifying production DGX services. If external endpoints are unavailable, provide contract-tested adapters and label live integration **unverified**.
