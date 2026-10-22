# Visual Mentor v3 — Live Video, Spatial Framing, Conversational Mentor and A2A Research

**Status:** implementation specification; no deployment authorization.  
**Date:** 2026-10-22  
**Source branch:** feature/video-rag-mentor-v2  
**Implementation branch:** feature/visual-mentor-v3-live (create from source branch HEAD; do not work on main).  
**Deployment target:** PRIVATE Hugging Face Docker Space on CPU Basic; no production changes without separate approval.  
**Prior specification:** docs/spec-v2-archive.md (preserved verbatim).  
**Primary principle:** extend the existing Video RAG and Visual Mentor v2 implementation, do not redesign or rebuild working features.

## 0. Precedence, evidence and hard constraints

This v3 specification supersedes v2 where the direction differs (remote-only STT, no recorded video, no research workers, limited conversation model). All v2 functional, UI-parity, access-control, configuration, provider-egress, data-integrity, encryption, provenance and rollback invariants remain mandatory unless explicitly modified here. Read docs/v2-release-readiness.md, docs/providers.md, docs/deployment-hf.md, docs/backup-restore.md, docs/github-backup-migration.md and current tests before coding.

Known v2 facts, not claims of production readiness:
- Library, Search, Ask, Experiments, Architecture, video details, Live, Models & Routing, Backups already exist.
- The Live tab supports two selected browser cameras, simulated sampled-frame submissions, exact-frame overlays, photo capture, freeze/fullscreen, push-to-talk and simple advisory guidance.
- Video RAG has CPU FFmpeg upload/ingestion, remote transcription and isolated remote text indexes; current size/duration limits are 64 MiB / 30 minutes.
- v2 already has a version-1 strict YAML schema, CAS apply/rollback, safe provider egress, partial-failure routing, parallel/sequential/fallback/conditional strategies, and bounded security tests.
- Research is only a placeholder Protocol in vrag/research.py; no implemented A2A dispatch. Existing Qwen conversation flow is not a durable chat/agent run engine.
- NVIDIA detection adapter uses a custom /detect gateway contract, demonstrated only with mocks. A generic NVIDIA API must NOT be assumed to match it.
- Laya's tested /v1/system-one image query is a narrow 'noul' scoring contract; one 64x64 synthetic-image test took about 22.6 seconds. It is NOT qualified for fast object geometry, temporal tracking, general captioning or sub-second decisions.
- Existing v2 resource probe: approximately 180 MiB idle RSS, 220 MiB sampled cgroup peak in synthetic 2-vCPU/16-GiB tests. These are not dual-camera/provider/Phonon benchmarks.
- Production/private HF deployment, physical dual-camera checks, real NVIDIA/embedding/STT tests and verified off-Space backup recovery remain gated.
- Current backup code uses encrypted private GitHub release assets; the latest report records live upload-host credential failure and HF access restrictions. No successful production recovery must be inferred.

**No changes to DGX services, existing vLLM/Ollama aliases, Tailscale, live HF Spaces, backups, credentials, internet port exposure, or production stores as part of code implementation.** All external integrations default disabled unless a live-tested and explicitly approved route has been configured. No user media is recorded or transmitted before explicit consent.

## 1. Target system

Browser on laptop:
- Integrated camera AND USB webcam simultaneously, independently selectable; device choices kept in browser-local preferences.
- Live native preview, mic, optional opt-in recordings, freeze/snapshot, per-camera object overlays, selectable tracked object and virtual stabilized auto-crop.
- Camera preview and tracking overlays remain responsive while network inference and research jobs are slow or disconnected.
- Original Video RAG UI/navigation and design system stay intact.

Private HF Docker Space:
- Next.js frontend and loopback FastAPI, one external application port 7860.
- Session, conversation, routing/configuration, video library, recording import, metadata/index, live observations, and outbound A2A job coordinator.
- Optional small **local Phonon-2 English ASR** worker (CPU) behind a feature flag; remote multilingual transcription fallback.
- No GPU, no locally loaded Qwen/Cosmos/detection VLM; FFmpeg for bounded media processing only; no Docker daemon/research containers running inside the Space.

External inference and agents:
- Main conversational model: Qwen/Qwen3.6-35B-A3B through an approved OpenAI-compatible endpoint, preferably existing DGX Ollama or vLLM gateway; configurable model and fallback, no hardcoded base URL.
- Detector + temporal tracker: qualified NVIDIA endpoint/gateway and/or browser tracking; NVIDIA/Cosmos-Reason2 for optional spatial-temporal analysis, not automatically an FPS tracker.
- Laya/Jev: fast vision *decision* candidate only after latency and output-contract qualification; NEVER fabricate boxes from semantic text.
- Research: outbound HTTPS A2A to independently hosted durable agents; no inbound public callbacks required.
- RAG: existing versioned Video RAG indexes, citation/timestamps, and optional remote embeddings.

### 1.1 Model truthfulness

Official Qwen3.6-35B-A3B weights expose text/image/video capability via supported runtimes, but do not treat it as documented native audio-in/audio-out; transcribe microphone audio first. OpenAI-compatible API does not guarantee that video, structured outputs, tool calls and streaming are supported identically on Ollama and vLLM. Capability probe and test each configured endpoint, with video-to-sampled-frame fallback. Published Ollama tag 'qwen3.6:35b-a3b' is an example, not evidence it is installed on the DGX.

Phonon-2 is English ASR, ~164-MB model download; CPU execution is supported but actual 2-vCPU HF performance/RSS/dependency footprint must be measured. It is optional and must not become a mandatory heavyweight dependency for the default Space build. Add supported German/multilingual remote ASR fallback by configuration. No claim that Phonon-2 is a speaker or text-to-speech model.

## 2. Explicit product features / UX contract

### 2.1 Live tab enhancements

Preserve existing two-camera lifecycle/consent, reconnection, stale-frame and privacy protections. Add controls for:
- Record video: Camera A / Camera B / both independently; optionally record local microphone after separate audio consent; start/pause/resume/stop where supported.
- Recording elapsed time, state, resolution, mime/codec support, byte count, and capture/encoding errors.
- Immediate local replay, download and delete; explicit per-recording action 'Import to Video RAG' with upload progress, indexing status, privacy note and ownership.
- Per-camera detection overlay: label, confidence, provider, optional stable track ID; click or keyboard-select an object.
- Framing: off / manual object selection / auto-select recommended object; crop margin, minimum crop, smoothing, lost-target timeout, reset, full-frame recovery, picture-in-picture display.
- Capture raw / annotated / cropped video as **separately labeled outputs**; never imply recorded overlays exist if only a CSS canvas preview was shown.
- Visual context summary fed to mentor; speech transcript and async research-job activity.
- Simple profile selector exposing configured model route per camera and ability to compare Laya vs NVIDIA or run both.
Keep tab keyboard-operable, accessible, responsive and styled with existing tokens/components. Original Library stays homepage.

### 2.2 Capture media constraints

Browser uses getUserMedia, enumerateDevices, MediaRecorder, Canvas/OffscreenCanvas or WebCodecs only where supported, with capability negotiation and graceful fallback. Prefer actual device stream for original, stable independent MediaRecorder pipelines. Do not depend on HF server receiving continuous 30 FPS media. Client-side optional side-by-side/PiP composite is a separate mode.

Recordings stay *browser-local by default* until explicit download or authenticated opt-in upload; media is not automatically backed up, transcribed, indexed, or sent to research workers. Show unsupported media formats. Enforce quotas and backpressure; current 64-MiB upload cap is authoritative until changed with security/storage tests. For larger recordings provide local file export and clearly explain upload limitation; no unbounded request bodies, no automatic hidden chunking bypass. Support loss of device, tab closure, disk quota, abort and inconsistent audio track handling. Request separate consent for video, audio, server upload, external provider vision and agent data sharing.

### 2.3 Tracking versus detection versus framing

- Detection: verified spatial model emits normalized bounding boxes in [0,1], labels and calibrated-or-unverified confidence; source dimensions and original capture timestamp.
- Tracking: assign persistent track IDs over frames using browser CPU tracker/association first, with deterministic lost/reacquired states and optional provider tracker when proven. Do not label per-frame detections as 'tracking'.
- Framing: select target ID, convert box to canvas crop region, smooth position/zoom, constrain edges and minimum dimensions, preserve aspect ratio, account for device rotation/mirror/object-fit contain/cover. On lost target expand to full frame rather than jump to unrelated object.
- NVIDIA adapter: verify actual model ID, invocation schema, normalizations and coordinate frames. Existing detection-http gateway supports exact /detect schema only; add adapter for an actual chosen upstream protocol after a protocol capture/synthetic test. Cosmos reasoning may enrich spatial decisions but must not be assumed to provide stable video tracker IDs.
- Laya: may rank which object to follow or whether a scene deserves deeper inspection, but cannot contribute spatial boxes without a documented, separately qualified geometry contract.
- Dual camera: independent frame IDs and capture timestamps, no unproven 3D synchronization/calibration; never fuse boxes across views without calibration.

### 2.4 Conversation and research UX

Provide a Mentor conversation panel with streamed Qwen responses, explicit tool/research status, cancel/stop, video RAG citations, camera observation references, compacted context and user-controlled session deletion/export. Research should show queued, running, waiting/input-required, completed, failed, canceled with a link to cited artifacts. Never block rendering or camera frames awaiting an A2A run.

## 3. Engineering workstreams and API contracts

### W0 — Audit and baseline (must precede refactors)

Review current branch code, feature config, tests, CSS/screenshot baselines, deployment/backup blockers and external provider contracts. Capture exact baseline HEAD; create isolated implementation branch/worktree from it. Produce docs/v3-baseline.md with what is already present, proposed diffs, risks and test commands. Do not reset/merge the donor branch or modify main.

### W1 — Browser video recording and virtual framing

Extend web/src/app/live/page.tsx incrementally; extract reusable CameraRecorder, TrackingOverlay, FramingController and RecordingPreview components/hooks where helpful. Keep camera stream ownership centralized and teardown deterministic; no duplicate getUserMedia calls for one selected source.

Recordings have stable IDs; local metadata includes camera slot(s), start/end, duration, MIME/codec, resolution, consent, approximate size and optional source observation IDs. Never send bare browser device IDs to the server as stable user identity.

Backend import reuses existing bounded ingestion job pipeline. If a new recording endpoint is introduced, it must delegate to existing upload/ingest path and existing user role; no new unauthenticated media handler.

W1 acceptance: two simulated cameras can preview and record independently; local replay/download/delete; unsupported browser/codec or device change managed; explicit upload imports video to original Library and triggers existing job status; cropped preview follows test track and correctly degrades on loss; no raw recording persists to Space without opt-in.

### W2 — Detection/tracking and model routing

Preserve config/schema.py version-1 files and semantic validation. Introduce a **versioned migration** for any v2 YAML fields (not silent acceptance of unknown keys); existing saved profiles remain readable, exportable and rollback-safe. Extend provider capability table with actual validated tracker/ASR/conversation/A2A capabilities. Keep strict allowlisted HTTPS destination and secret-name references, no arbitrary URL/plugin execution from YAML.

Proposed new route roles:
- live.camera1.detection; live.camera2.detection; live.cameraN.decisions
- live.tracking (local-browser or remote verified tracker)
- live.framing.target_selection
- live.temporal_reasoning
- mentor.conversation
- audio.transcription
- research.dispatch
Every enabled route must be backed by a valid typed adapter and tested capability. Parallel, sequential, fallback and result fusion preserve frame_id, camera_id, config_version, provider source and failure codes. Camera session overrides remain nonpersistent and respect privacy tiers.

For example, non-executable illustrative configuration (must be adapted to real schema and confirmed endpoint IDs):

    version: 2
    profile: v3-lab-disabled
    providers:
      qwen:
        adapter: openai-chat-vision
        model: qwen3.6:35b-a3b
        base_url_env: VM_QWEN_GATEWAY_URL
        api_key_secret: VM_QWEN_GATEWAY_KEY
        capabilities: [image_understanding, reasoning]
        trust: approved_sensitive
      nvidia:
        adapter: detection-http
        model: VERIFIED_DETECTOR_MODEL_ID
        base_url_env: VM_NVIDIA_DETECT_URL
        api_key_secret: VM_NVIDIA_API_KEY
        capabilities: [object_detection, bounding_boxes]
        trust: approved_sensitive
      laya:
        adapter: laya-vision
        model: thaitea/laya-vision
        base_url_env: VM_LAYA_URL
        api_key_secret: VM_LAYA_KEY
        capabilities: [image_understanding, visual_decision]
        trust: approved_sensitive
    features:
      live.camera2.detection:
        enabled: false
        strategy: parallel
        providers: [nvidia, laya]
        result_policy: all
        fusion: spatial_semantic
      mentor.conversation:
        enabled: false
        strategy: single
        providers: [qwen]

The real config template must use approved environment variable names and the schema actually implemented. Do not activate placeholder IDs. For a Qwen conversation adapter support text-only streaming and validated tool calls; a visual adapter may reuse an approved endpoint if the provider supports both.

W2 acceptance: schema migration and rollback preserved; detector/tracker contracts and mirrored/cover geometry tests pass; Laya produces no forged geometry; profiles switch between Laya-only, NVIDIA-only and parallel with provenance; no unsafe network egress.

### W3 — Conversational Qwen3.6-35B-A3B

Implement durable-enough conversation/session contracts with Qwen through existing provider abstraction, configurable Ollama or vLLM OpenAI-compatible gateway and server-side secrets. Do not load Qwen weights in HF Space. Need:
- Streaming SSE or existing sanctioned same-origin transport, cancel/timeout/reconnect semantics; no public raw model endpoints.
- Bounded conversation turns and explicit summarization provenance; model summaries cannot overwrite authoritative observations, consent or research result metadata.
- Typed tool registry: dispatch_research, get_research_status, cancel_research, retrieve_video_evidence, optional summarize_scene. Tool functions executed only on validated model tool calls with authenticated user/session and policy checks.
- Idempotency and dedup for replayed tool calls; maximum concurrent calls and recursion budget; missing/invalid tool call fails closed with observable error.
- Snapshot relevant observations, recording/video references and retrieved citations into each turn; no unconsented full-video uploads to Qwen.
- Provider capability probing: Ollama tag/version vs vLLM model ID; verify chat streaming, tools, structured outputs, image handling separately. For video input, support endpoint-native protocol only if independently verified; otherwise use timestamped sampled frames.

W3 acceptance: fake provider streaming/tool fixtures; malformed and duplicate call rejection; offline/disconnect/cancel; cited grounding; switching Ollama/vLLM without schema mutation; tests confirm no camera frames sent to an unapproved provider.

### W4 — Optional Phonon-2 CPU ASR

Implement behind VM_LOCAL_PHONON_ENABLED=false by default. Optional image/build profile or install extra so default HF runtime does NOT download weights or pull heavyweight frameworks. Use official Phonon CPU engine (actual pinned version/licensing) and 16kHz English audio input via FFmpeg/WebAudio conversion; preserve strict bounded audio upload and single process/worker concurrency. Keep public microphone consent and loopback-only Phonon service or in-process isolated worker. Do not expose another public port. Gate lazy init, shutdown, no uncontrolled model downloads and no secret leakage.

Do not assume Phonon outputs German; define optional approved remote multilingual ASR route for non-English audio. Transcript-only Qwen handoff. Keep existing remote Whisper-compatible STT as optional fallback, not mandatory.

W4 acceptance: disabled build boots without Phonon/torch; enabled build loads on CPU with bounded memory, makes valid English transcript from authorized microphone/file, rejects oversize/unsupported audio; measures concurrent two-camera p50/p95 and RSS; user-visible degraded state if startup fails. Real 2-vCPU result is a qualification gate.

### W5 — Research through outbound A2A HTTPS

Use official a2a-python SDK for the **client adapter** with pinned compatible protocol/spec. The Space dispatches outbound to approved external research agents; Spynel is *optional external task supervisor*, not a runtime dependency. Do not implement a proprietary A2A protocol or run external Docker agents inside the Space.

Respect Agent Card identity/auth/capabilities, allowlisted TLS HTTPS agent destinations, authentication/credential scope, response schema/size, timeouts, job idempotency and backpressure. Do not let model output choose arbitrary URLs. Dispatched task payload contains a concise bounded research question, permitted context/ref IDs and explicit privacy tier—not full raw frames/audio by default.

Stable job contract, proposed internal API (names may be adjusted without breaking existing public APIs):
- POST /api/mentor/conversations ; POST /api/mentor/conversations/{id}/turns ; GET /api/mentor/conversations/{id}/events
- POST /api/research/jobs ; GET /api/research/jobs/{id} ; POST /api/research/jobs/{id}/cancel ; GET /api/research/jobs/{id}/artifacts
- Research job: job_id, user/session, goal, agent_id, config_version, A2A task_id/context_id, idempotency_key, status, attempts, created_at, updated_at, last_error, provenance, permitted_refs.
- Immediately return an accepted job ID to the mentor. Qwen continues conversation while research runs. Reconcile remote task state by outbound polling / SDK streaming when safe; no unauthenticated inbound webhooks or new public routes. Store durable job state in existing SQLite/backup scope; use resume/reconcile after application restart. Research result is advisory evidence, not authoritative permission to act.
- Terminal results carry citations, URLs, retrieval timestamps, confidence/limitations and producer identity. Clearly distinguish verified primary evidence from model-written summary and reject unsourced factual assertions for high-stakes guidance.
- Cancel local tasks and, if supported, propagate remote A2A cancellation; reconcile unknown/ambiguous dispatch outcomes without double execution.

W5 acceptance: mocked real SDK client transport against a local fixture A2A server; dispatch/get/cancel, partial failures, retries, duplicate idempotent calls, long-running completion while streaming chat, app restart/reconcile, no provider credential logs; live real agent not claimed until qualified.

### W6 — Reliability, security, release evidence

- Keep v2 authentication/CSRF/origin, sensitive routing, SSRF/DNS rebinding protection, read/role restrictions, secret references, profile CAS/rollback, no arbitrary uploaded YAML execution, recording privacy and encrypted backup compatibility.
- Permission per operation: preview, raw frame provider inference, recording, audio, save/upload, external A2A research attachments. Private HF visibility alone is not app-level authorization.
- Preserve original Library/Ask/Search/Experiments/Architecture and clip Range support. Existing 109+ backend and browser test baseline must not regress; record actual observed test count on this branch instead of hardcoding 109 as target.
- Synthetic dual-camera/virtual-geometry/recording, offline provider, parallel Laya+NVIDIA, Qwen streaming/tool execution, speech enable/disable and A2A tests. Real-device/browser matrix for laptop+USB and HTML media MIME variations. Validate production Next build, lint, backend pytest, Playwright and CPU Docker.
- Instrument per-stage latency (capture→send→detect→track→overlay, audio→transcript→first mentor token, A2A acceptance→completion), p50/p95, error rate, CPU/RSS, payload size, real provider usage/cost and privacy-denial counts. Never invent unmeasured performance.
- Browser live preview target 15–30fps where device/browser supports; sampled remote inference starts <=2fps/camera and is adaptive. Tracking can run at browser frame rate, with stale-input/reprojection guards. Hard SLA deferred until physical-provider tests.
- No public HF staging, Space upload, production change, GitHub Actions activation, backup migration, provider key setup, DGX service start/stop, model pull or Docker infra changes without separate authorization. A dry-run/isolated synthetic test is okay.
- Preserve outstanding v2 blocker reporting: HF private authentication access, 12-hour encrypted GitHub recovery, actual uploads.github.com auth and live third-party inference checks.

## 4. Source layout (guidance, not compulsory exact names)

Keep FastAPI + Next.js and existing module boundaries. Possible additions:

    web/src/components/live/CameraRecorder.tsx
    web/src/components/live/TrackingOverlay.tsx
    web/src/components/live/FramingViewport.tsx
    web/src/components/live/RecordingReview.tsx
    web/src/components/mentor/ConversationPanel.tsx
    web/src/components/mentor/ResearchJobList.tsx
    vrag/conversation.py
    vrag/tracker_contracts.py
    vrag/phonon_adapter.py
    vrag/a2a_client.py
    vrag/research_jobs.py
    config/examples/v3-disabled.yaml
    docs/v3-baseline.md
    docs/v3-qualification.md
    tests/ (backend fixtures and deterministic fake endpoints)
    web/tests/ (Playwright camera, recording, framing and chat tests)

Prefer well-factored extensions to existing vrag/mentor_api.py, vrag/providers.py, vrag/routing.py, vrag/research.py and existing tests. Do not build two independent settings systems or two separate video upload pipelines.

## 5. Delivery order and stop conditions

Gate 00: baseline audit, protocol decisions, schema migration design and tests for existing branch. Produce explicit findings.
Gate 01: record/review/download and local framing with synthetic detections (no external model required).
Gate 02: tracker/detector provider contracts + YAML profiles; mock Laya and NVIDIA; evidence.
Gate 03: Qwen chat streaming and tool-call execution with fake OpenAI provider; no actual DGX modification.
Gate 04: optional Phonon CPU-ASR boundary and English fixture; local benchmark if dependencies available.
Gate 05: outbound A2A agent client + durable research state; mock agent / full loop.
Gate 06: end-to-end CPU Docker/simulated-browser tests and release-readiness report. Staging/live gates remain BLOCKED absent approvals and credentials.

For each gate: docs, tests, pass/fail evidence, exact commits and known issues. Prefer small reviewable commits. Stop immediately on unsafe side effects or a missing required secret/remote permission; continue with mocks and mark external steps BLOCKED, not PASS.

## 6. Definition of done

Code readiness requires: original Video RAG behavior preserved; dual-camera video record/replay/import available and consentful; selectable, stable object framing from verified boxes; no fabricated Laya geometry; flexible routed detectors and Qwen conversation with tool calls; optional off-by-default Phonon-2 ASR; A2A research dispatch with durable jobs, asynchronous completion and citations; strict private trust boundaries; executable tests; and a validated CPU-only Docker build.

Production readiness additionally requires independent approval and successful real HF private access/physical USB+integrated camera/provider qualification, resource measurement, encrypted backup/recovery drill, and rollback test. No code-complete gate authorizes production deployment.

## 7. Sources and precedence references

- Existing project: https://github.com/JsonLord/basic-video-rag-with-embeddinggemma2
- v2 historical product requirements: docs/spec-v2-archive.md
- v2 implementation status: docs/v2-release-readiness.md
- Existing provider protocols: docs/providers.md
- Private HF release runbook: docs/deployment-hf.md
- Backups: docs/backup-restore.md and docs/github-backup-migration.md
- Qwen official model: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Ollama Qwen example: https://ollama.com/library/qwen3.6/tags
- Phonon model and CPU notes: https://huggingface.co/FermionResearch/Phonon-2 ; https://github.com/fermionresearch/phonon/blob/main/docs/cpu.md
- Official A2A SDK: https://github.com/a2aproject/a2a-python
- Optional orchestration comparison: https://github.com/agent0ai/spynel
