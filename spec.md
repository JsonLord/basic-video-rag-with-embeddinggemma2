# Visual Mentor v2 — Video RAG–First Product Specification

**Status:** proposed replacement specification (2026-10-16)  
**Repository:** https://github.com/JsonLord/basic-video-rag-with-embeddinggemma2  
**Recommended development branch:** `feature/video-rag-mentor-v2`, newly branched from `main` (`7f8922cad8adb7e73a5f95ecfbf5b1a73e5bd46f` at review time; verify current remote HEAD before branching).  
**Reuse source:** `feature/visual-mentor` at `245b686c916f0fcb0aff50b305e27f399c32910d`.  
**Deployment target:** existing `Leon4gr45/openweb` Hugging Face Docker Space, **private**, subject to explicit deployment approval. **Do not overwrite** this deployment until a UI parity review and staging approval.

## 0. Direction reset / decisive product rule

This project is **the original Video RAG app, enhanced with Live Visual Mentor**, not a new lightweight mentor dashboard. The UI/UX design authority is the original `main` branch's `web/` application. Preserve and improve the established dark palette, page widths, typography, navigation, cards, charts, source citations, clip playback, retrieval controls and information density. New features must look and behave like native extensions of that site. Do **not** replace it with generic forms, a blank dashboard, a Gradio UI or a route-only API shell.

The original Video RAG is not a demo to discard: its 30-second segmentation, video library, clip seeking, timestamped search results, per-view retrieval, RAG answers, experiments and Matryoshka evaluation are important product assets. Build on top of those capabilities. The first-page experience must not collapse to a configuration editor, camera controls or an empty-state screen.

**Explicitly abandon the previous optimization target of <1 GB memory and ~1 vCPU application load.** Fit the provisioned Hugging Face **CPU Basic: 2 vCPU, 16 GB RAM, 50 GB ephemeral disk**. Take advantage of RAM for caches, metadata, indexes, thumbnails and process separation; continue using remote inference for large AI models. Memory does not create extra CPU capacity; use queues, adaptive video sampling and bounded FFmpeg jobs. Do not require local GPU or DGX Spark.

## 1. Verified repo/branch facts and migration decision

- `main`: original Next.js 16 / React 19 / Tailwind video RAG frontend, with Library at `/`, Search, Ask, Experiments, Architecture and video-detail/clip player. Original color tokens include `--page`, `--surface`, `--surface-2`, `--text-primary`, `--text-secondary`, `--accent`.
- `feature/visual-mentor`: 14 commits ahead of main at review; implemented tested camera UI, remote adapters, YAML routing, runtime and authorization. `docs/release-readiness.md` reports 77 backend and 12 mocked-browser tests, plus successful synthetic live Laya inference, but not actual HF/USB/NVIDIA/Whisper qualification. Preserve this as an implementation donor, not the UI baseline.
- `deploy-huggingface-space-2826124284938220779`: one additional commit beyond `feature/visual-mentor` (PR #1, deployment setup, extra Next config). This is **not** the architecture or design baseline. Audit its deployment changes individually; avoid conflicting `next.config.ts` and `next.config.mjs`.
- The original `main` `spec.md` describes the previous ultra-light direction. **Replace that specification on the NEW development branch only** with this file. Do not rewrite `main` or merge legacy branches prematurely.

Implementation rule: create the new feature branch from `main`; preserve its `web/` markup/components/styles as the source of truth. Port tested infrastructure from `feature/visual-mentor` by *selective file-level migration or careful cherry-picking with UI hunks rejected*. Do not merge the entire prior feature branch blindly, and do not discard backend test coverage.

## 2. Product vision and primary user journeys

**A. Browse and learn from videos** — Landing page is the original enriched Library: thumbnails, source titles, metadata, durations, previews, indexing status, filters and recent content. Open a video-detail page, inspect segments/transcripts/keyframes, seek to cited moments, and return to search/Ask with context.

**B. Search across videos** — Keep text, frame, video, audio, fused and hybrid retrieval views whenever a compatible index exists. Expose model identity, indexing state, vector dimensions and honest unsupported states. Search by natural language and, when a real cross-modal embedding provider supports it, by uploaded image. Display sources and timeline markers.

**C. Ask / Video RAG** — Ask questions about indexed clips; retrieve evidence, answer via external multimodal LLM, cite exact clips and timestamps, allow inline playback. Provider selection should not break retrieval or silently substitute false multimodal semantics.

**D. Live Mentor** — Add a polished `Live` workspace whose visual language matches original Video RAG. From the laptop browser, capture built-in and USB cameras concurrently (where OS/browser permits), show dual video previews, overlays and observations, select inference routes, get step-by-step advisory guidance, push-to-talk to remote Whisper. Link selected observations to current video research and saved sessions.

**E. Models & Routing** — A professional configuration studio added to the original navigation, not the homepage. Declare remote providers, assign models to functions, upload/edit/export a `.yaml` / `.yml` profile, test connections, preview changes, apply/rollback safely, and show traceable concurrent provider results (e.g., Laya and NVIDIA operating on the same frame).

**F. Import / Ingest** — Upload media into the Library and create/refresh searchable segments and thumbnails using local CPU FFmpeg when appropriate. Remote transcription, embeddings and VLM enrichment must run as bounded background jobs with status and retries; never block the web UI.

## 3. UI / experience specification — highest priority

### 3.1 Original UI as invariant

Before code changes, capture baseline screenshots at desktop (1440px), laptop (1280px), tablet and mobile for `/`, `/search`, `/ask`, `/experiments`, `/architecture`, `/videos/[id]` using seeded fixtures. Inventory the actual components, typography, colors, card metrics, chart styles, page gutters and clip-modal interactions. Establish screenshot regression tests. Do not copy the currently deployed `openweb` styling as a reference.

Preserve the original component-level UI: `web/src/components/Nav.tsx`, `NavLinks.tsx`, `Controls.tsx`, `ClipPlayer.tsx`, `web/src/app/Library.tsx`, Search/Ask views, video details and charts. Changes may improve usability and responsiveness, but original workflows, content density, look and affordances must remain recognizable. Reuse existing Tailwind tokens and component patterns. Avoid generic `.vm-panel` / `.vm-button` aesthetics if they clash with the original design; replace those with shared design-system primitives matching existing page cards/controls.

### 3.2 Navigation and site map

The canonical primary navigation is:
- **Library** (`/`, original landing page)
- **Search** (`/search`, existing)
- **Ask** (`/ask`, existing; includes source-aware mentoring questions)
- **Live** (`/live`, new first-class workspace)
- **Experiments** (`/experiments`, existing)
- **Architecture** (`/architecture`, existing)
- **Models & Routing** (`/models`, new; may live in a visually coherent Settings group if width demands it)

Maintain video-detail pages and clip-modal navigation. The logo/name can become `Video RAG · Visual Mentor` without losing context. Navigation must work with keyboard and narrow widths; prioritize meaningful content over settings clutter.

### 3.3 Live workspace wireframe (visual guidance, not prescriptive CSS)

```
Top: original Video RAG navigation
Page title: Live Visual Mentor      [Camera profile ▼] [Routing profile ▼] [Session status]
┌─────────────────────────────┬─────────────────────────────┐
│ Camera A • laptop           │ Camera B • USB              │
│ full native preview         │ full native preview         │
│ boxes / track IDs           │ boxes / track IDs           │
│ device • resolution • FPS   │ device • resolution • FPS   │
│ Start / Stop / Share toggle │ Start / Stop / Share toggle │
└─────────────────────────────┴─────────────────────────────┘
┌─────────────────────────────┬─────────────────────────────┐
│ Scene timeline              │ Mentor guidance             │
│ detections / scores /       │ goal, step, next action,    │
│ frame stamps / model source │ supporting video citations  │
└─────────────────────────────┴─────────────────────────────┘
Bottom: Push-to-talk / transcript, active routes, errors/latency,
        recent snapshots and links to Search / Ask / video clips.
```

Support side-by-side/stacked layouts, fullscreen camera focus, overlay toggle, photo capture, freeze-frame for inspection, timeline scrubbing, visible camera permission/connection states, accessible control labels, informative onboarding and attractive empty states. Never auto-start capture. Never advertise 'tracking' if upstream results contain only per-frame detections without persistent track association.

### 3.4 Models & Routing studio wireframe

```
Models & Routing
[Active profile ▼] [Save as] [Import YAML] [Export] [History/Rollback]
Provider cards: Laya | NVIDIA | Whisper | Cloud VLM | Embeddings | Custom
Feature matrix: Camera A/B scene | detect | track | mentor | STT | RAG | ingest
Route detail: single / fallback / parallel / sequential / conditional
Visual graph: Camera B → NVIDIA detector → Laya → mentor
YAML editor / schema errors / side-by-side diff
[Test synthetic] [Dry-run] [Apply]   Trace + latency + error details
```

Offer **both** a form-based route builder and raw YAML editing. YAML upload populates editor and preview but does not apply immediately. Show endpoint URLs (redacted only where they reveal secrets), model IDs, protocol/capabilities, privacy authorization, expected payload type, cost/latency hints and destination status. Provider selection can be overridden for a single live session without changing the global default when safe. Support `Laya only`, `NVIDIA only`, `Hybrid parallel`, `NVIDIA→Laya`, `Fallback`, `Custom` preset profiles.

## 4. Runtime architecture for HF CPU Basic

```
Browser HTTPS (laptop integrated + USB camera)
   └── Original Next.js UI + Live + Models editor
           └── same-origin /api and /media
                  ├── Next.js web server (or suitable build output)
                  └── FastAPI backend (private loopback)
                         ├── Video Library, upload, segmentation, thumbnails
                         ├── FFmpeg bounded background ingestion workers
                         ├── transcript and metadata DB / index manager
                         ├── NumPy search, MRL/RRF where compatible
                         ├── remote provider registry and feature router
                         ├── live-session coordinator, fusion, provenance
                         └── authorized outbound HTTPS inference endpoints
                                  ├── Laya/Jev
                                  ├── NVIDIA detection/tracking (verified adapter)
                                  ├── Cloud VLM and mentor LLM
                                  ├── Whisper-compatible STT
                                  └── Text / multimodal embeddings
```

Use Docker, Python FastAPI and original Next.js (do not switch UI stacks). One externally exposed port `7860`; FastAPI stays on loopback or behind the same-origin gateway. Keep the Node server if needed for Next SSR; static export only if all existing UI/route behavior remains intact. Local FFmpeg and libraries are permitted for **media processing**; local GPU inference or large model weights are not required. Allow optional small CPU helpers (image hashing, VAD, keyframe extraction, simple tracking/association) if benchmarked; no blanket exclusion of `onnxruntime`/OpenCV/other reasonable CPU libraries.

**Resource budgets (soft, measured rather than ideological):** target <8 GB memory in a normal dual-camera + moderate-index workload and keep at least 3–4 GB headroom; maximum under actual 16 GB cgroup. Background job concurrency defaults to 1–2 on 2 vCPU, adjustable through config; bounded queues and upload sizes; no unbounded 30 FPS cloud inference. Benchmark UI latency, FFmpeg throughput, startup, frame-to-overlay p50/p95, memory and provider-cost estimates. No artificial 200 MiB target.

**Durability:** 50 GB base disk is ephemeral. Do not assume mounted persistent storage exists. Check current HF account/Space capabilities; external S3-compatible object store or private HF Dataset (with appropriate access controls) can hold video assets/index snapshots; external durable database if necessary. Store auth-sensitive runtime config in approved durable storage, backup/recover, never write API secrets into snapshots. Library data should survive Space rebuild/restart if persistence is configured; without it, warn explicitly. Verify runtime storage rather than trusting historical docs.

## 5. Video RAG enhancement (must recover original product value)

- Keep ingestion pipeline concepts: upload/import, media proxy generation, thumbnail/keyframes, ~30-second timestamp-aligned segments, transcripts, embedding/metadata manifests, retrieval views and RAG answers.
- Add video import UI and asynchronous jobs: upload progress; deduplication; FFmpeg transcode/seek-friendly proxy; remote Whisper transcription with timestamps; segment/keyframe extraction; remote image/video embeddings when supported; retry/resume/cancel; re-index status and audit trail.
- Use remote **text embeddings** for transcripts/captions. For genuine `frame`, `video`, `audio`, `fused` views, use a **verified compatible multimodal embedding family** providing the requisite shared space. Text-only vector similarity cannot masquerade as cross-modal retrieval. If missing, show disabled/unavailable view, explanation and setup path; retain legacy read-only manifests where compatible.
- Version vector indexes by provider, model, modality/view, dimension, preprocessing and segmentation version. Re-embed on changes, never mix incompatible vectors; enforce valid MRL dimensions and renormalization if model supports truncation.
- Keep reciprocal-rank fusion, source provenance and timestamps; avoid lowering retrieval quality just to remove ML dependencies.
- VLM answer adapter: send provider-supported image frames/transcripts/audio payloads; no `file://` references to remote APIs. Use strict caps on frames per retrieved clip and detailed citations.
- Maintain evaluation/experiments UI: synthetic and manual queries; recall@k and per-view comparisons only when results are genuinely comparable; preserve old experiment history with model labels and data provenance.
- Support a populated demo library or **realistic seeded fixture library** when no production corpus exists, clearly marked as sample content. No broken empty dashboard on first launch.

## 6. Browser dual-camera and live perception

- Use `navigator.mediaDevices.getUserMedia`, `enumerateDevices`, `devicechange`, `MediaStreamTrack` lifecycle; browser owns webcams. Physical laptop and USB cameras are selected on the user machine, never inside the HF container.
- Camera A/B can run independently or simultaneously, subject to physical and browser permissions; retain device selection in browser-local state (device IDs are not portable YAML config).
- Browser always renders fluid preview. Transfer only explicitly authorized sampled frames/crops. Configurable JPEG/WebP quality, FPS and resolution; adaptive backpressure, per-camera maximum outstanding requests, cancellation on stop, stale frame/route revision rejection, stop when browser tab hidden when appropriate.
- Bounding boxes are accepted only from a verified spatial detector/tracker output. Normalize coordinates with source dimensions, account for contain/cover, mirror, resize and orientation; show confidence, label, provider provenance and optional track ID. Laya decisions never become synthetic boxes.
- Split detector (spatial), tracker (temporal identity), Laya (rapid visual decisions), VLM (complex interpretation), mentor (advice); permit other provider capability combinations where validated.
- Provide timestamped camera/frame IDs for multi-view synchronized observations; never infer scene calibration or 3D geometry from two unsynchronized views.
- Remote Whisper push-to-talk and uploaded-video transcription; optional voice feedback only if a configured speech synthesis provider is available.
- No default recording or long-term saving of live frames; session snapshots require explicit save and clear retention rules.

## 7. Flexible inference and YAML routing

**Port and improve** prior `config/schema.py`, `vrag/providers.py`, `vrag/routing.py`, `vrag/mentor_api.py`, `vrag/egress.py`, configuration tests and live-safety guards from `feature/visual-mentor`, while adapting interfaces to the original UI and new feature map.

Provider configuration supports: friendly label, adapter/protocol, endpoint environment reference, model identifier, capabilities, payload schema version, supported modalities, auth **secret reference**, timeouts, concurrency, max payload, allowed destinations, privacy tier, cost metadata, test status. Validate credentials only server-side; never write them into YAML.

Routing strategies: `single`, `fallback`, `parallel`, `sequential`, `conditional`, and typed `ensemble` only where defensible. Parallel Laya+NVIDIA returns independent provenance-preserving outputs; result fusion combines semantically compatible fields without forging detections. Partial provider failures do not erase valid results. Include `all`, `first_valid`, or quorum policy where supported. Sequential passes typed outputs explicitly, not arbitrary prompt concatenation. Thresholds need calibration and policy documentation.

**Security:** safe YAML loader, strict schema and migration version, 64KiB default file limit, schema lint and preview diff, authorized apply, compare-and-swap version, snapshot/rollback, deny SSRF/private hosts, redirect-safe pinned resolution or vetted egress proxy, per-destination sensitive-camera authorization checked again after fallbacks/parallel dispatch, secret redaction, request quota/concurrency, safe errors. HF private visibility is necessary but not sufficient for app-level authorization.

Example (illustrative; Codex must migrate to actual validated schema):

```yaml
version: 2
profile: hybrid-lab
providers:
  laya:
    adapter: laya-vision
    base_url_env: LAYA_BASE_URL
    api_key_secret: LAYA_API_KEY
    model: thaitea/laya-vision
    capabilities: [visual_decision]
    trust: approved_sensitive
  nvidia:
    adapter: detection-http
    base_url_env: NVIDIA_DETECTION_BASE_URL
    api_key_secret: NVIDIA_API_KEY
    model: VERIFIED_NVIDIA_DETECTOR_ID
    capabilities: [object_detection, bounding_boxes]
    trust: approved_sensitive
  whisper:
    adapter: openai-transcription
    base_url_env: WHISPER_BASE_URL
    api_key_secret: WHISPER_API_KEY
    model: VERIFIED_WHISPER_ID
    capabilities: [transcription]
    trust: approved_sensitive
  cloud_vlm:
    adapter: openai-chat-vision
    base_url_env: VLM_BASE_URL
    api_key_secret: VLM_API_KEY
    model: VERIFIED_VLM_ID
    capabilities: [image_understanding, reasoning]
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
  live.visual_decision:
    strategy: fallback
    providers: [laya, cloud_vlm]
  audio.transcription:
    strategy: single
    providers: [whisper]
```

The existing live Laya contract has only been qualified with synthetic frames and an advisory fixed question; inspect the actual upstream schema and do not claim free-form scene captioning or object localization without evidence. NVIDIA and Whisper require real endpoint qualification; placeholder model IDs are never deployable defaults.

## 8. HF Space deployment and existing openweb remediation

Target `https://huggingface.co/spaces/Leon4gr45/openweb` only after user approval. Do not assume the current deployment's content, access mode or source tree can be inspected remotely without credentials; verify via HF repo/API and browser screenshots. **Space must be private**, not merely a private GitHub development branch. Before deployment: back up existing HF Space repo/config/data, capture current screenshots, verify secrets, and prepare rollback commit. Publish from the new reviewed branch using the approved HF deploy method. Keep only application port 7860 public via HF; no additional exposed ports.

Do not merge PR #1's deployment branch wholesale: audit `.hfignore`, README metadata, `vrag/api.py` OpenAPI changes and `web/next.config.mjs`. Ensure exactly one authoritative Next config and functional `/api`, `/media`, range seeking, health checks, frontend routes and HF reverse proxy host settings. A private Space should reject anonymous page, API and media access; test actual private-app access with a logged-in browser.

Provide a visible health/status UI for absent provider credentials, storage, indexing and access. No production data migration without backup; no public video upload endpoints without user/app authorization. Do not publish/demo with misleading provider readiness badges.

## 9. Mandatory private GitHub backup every 12 hours

**Requirement:** Create a **separate private GitHub backup repository** (suggested name: `JsonLord/visual-mentor-backups`, unless an existing private repository is explicitly selected). Do **not** use the public application source repository as the destination for private user data. Repository creation, credentials, and activation require an authorized account/explicit confirmation; never claim that a workflow is active based only on generated files.

### 9.1 Schedule and execution boundary

- **Primary scheduler:** GitHub Actions in the **private backup repository**, not an in-process timer inside the HF Space. Use `on: schedule` with `cron: '17 0,12 * * *'` (UTC: every 12 hours) plus `workflow_dispatch` for immediate manual backups and testing. Scheduled Actions may run late or occasionally be skipped; treat **12 hours as the target cadence**, not a hard real-time guarantee. Add a stale-backup alert based on the actual successful-backup timestamp.
- **Primary data source:** Snapshot the **durable backing store** (approved private object store/database) instead of treating the Space's ephemeral filesystem as the only source of truth. If a protected Space export endpoint is used for derived state, authenticate through the HF private-access layer **and** an application-level short-lived/read-only export credential, verify it in a live staging test, and never expose unauthenticated dump URLs.
- **Concurrency:** One backup per environment at a time (`concurrency` group); retry transient failures with bounded backoff; never record a success when an upload, checksum verification, or manifest write failed. Missed schedules must be visible and manually recoverable.
- **Offline/sleep behavior:** The Action must not silently report success if the Space is sleeping/unreachable. Prefer direct reads from external durable state; if an export endpoint is unavoidable, report failure/blocked state, retry safely, and alert. Do not wake or mutate production without approval.

### 9.2 Backup scope, confidentiality and storage limits

Include versioned, consistent snapshots of:

1. Model provider and route YAML profiles, including configuration history/rollback versions, **with no plaintext credentials or camera data**.
2. Application SQLite/metadata databases (use SQLite online-backup API or another transactionally consistent snapshot, never a live `.db` file copy), video/segment metadata, transcripts/captions, ingest/research job state, and saved non-sensitive mentor settings.
3. Versioned search/index manifests and manageable vector index artifacts, identified by embedding provider/model/dimensions and corpus revision; include enough information to recreate indexes if omitted by a size policy.
4. Source deployment identifiers, Space revision, schema version, backup format version, timestamps, counts, SHA-256 checksums and a complete **backup coverage manifest** (including excluded classes/objects and why).

**Large original/proxy videos, audio and image assets** must be backed up to a private durable object store (or explicitly budgeted Git LFS if appropriate), NOT silently shoved into normal Git history. Store cryptographically verifiable asset inventory, object-store location identifiers and integrity hashes in the private GitHub backup repository. For a full restore, verify the object copies really exist and are accessible; a metadata-only backup is never advertised as a full media backup. Avoid GitHub's per-file Git limits, runaway repository history and unbounded Actions artifact usage. Apply explicit snapshot-retention and pruning policies (suggested: 14 days of 12-hourly snapshots, 8 weekly, 6 monthly, adjustable), without deleting the most recent known-good copy; document storage/cost implications.

Backups must be **encrypted before entering GitHub**, even though the target repo is private. Recommended: an age recipient/public key configured for backup encryption; the private decryption key is stored independently of GitHub and the Space (offline/secure secret manager) and is never committed or logged. For encrypted binary snapshots, avoid storing secret plaintext in manifests, logs, Git diffs, GitHub Actions artifacts or issue alerts. Use a minimal-permission scoped credential/GitHub App where cross-repository reads or writes require it; the backup repository's workflow may write to its own repository using tightly scoped `GITHUB_TOKEN` `contents: write` permissions. Use protected repo settings, minimal access, no public releases or Pages. Do not grant broad `repo` PAT scope by default.

### 9.3 Implementation interfaces and UI

Implement a reusable backup/export service (e.g. `vrag/backup/`) and a self-contained runner (e.g. `scripts/backup_state.py` and `scripts/restore_state.py`). Add a private workflow at `.github/workflows/backup-12h.yml` in the **backup repository** (provide a documented installation/template path from the application source repo). Keep backup configuration separate from inference YAML, so importing model profiles cannot change backup destinations or tokens. Expose **admin-only status** in the existing UI's Settings/Models administration area: last attempted backup, last verified success, age, checksum/coverage result, failure reason and manual trigger instructions. A manual UI trigger, if added, must require administrator authorization and must not bypass GitHub schedule/approval controls.

Implement `backup → upload → verify → manifest → report` and `list → download → verify checksums/signature/decrypt → dry-run → restore` flows. Restoration must support selecting a snapshot, checking compatibility, staging restored state in an isolated destination, verifying indexed media references and atomically promoting only after explicit operator confirmation. Never overwrite production state merely by running an automated test. Write `docs/backup-restore.md` with secrets provisioning, retention, alerting, data coverage, GitHub repo creation (private), operational costs and exact restore procedure.

### 9.4 Mandatory qualification gates

- Unit tests: consistent database snapshot under concurrent writes; excluded-secret scanning; no raw camera uploads; missing/corrupt asset detection; encrypted manifest/archives; size thresholds; failed exports and retries; no false success.
- Integration tests: a **manual `workflow_dispatch`** run in the private backup repository produces a real encrypted snapshot, checksums, asset manifest and successful commit; simulated failure is visible and alerted; successful restore into clean temporary storage produces equivalent content and expected indexes/config revisions.
- Resilience tests: Space container recreation or full rebuild does not eliminate the only copy of state; stale-backup monitor detects a deliberately missed schedule; retention does not remove the newest restorable backup.
- Sign-off: show private repository visibility, backup history/timestamps, contents (redacted), exact scope/exclusions, restore verification evidence, and the difference between GitHub metadata backup and external media backup. **Do not mark v2 deployed/fully backed up until an actual off-Space restore test passes.**

## 10. Phase milestones and evidence gates

**P0 — Evidence/branch safety.** Inspect all three branches, screenshot baseline UI, snapshot existing Space if accessible; create new branch from main; write porting map and no-regression matrix; verify latest commit IDs. No production mutation.

**P1 — UI parity foundation.** Original Library, Search, Ask, Experiments, Architecture, video-detail and ClipPlayer fully work and look like `main`. Add graceful seeded corpus/demo. Screenshot comparison baseline. This phase is a blocking gate.

**P2 — Remote inference + real RAG.** Port tested provider/security/routing backend from feature; preserve existing original API contracts or supply backward-compatible adapters. Remote text embeddings, video-source citations, answer generation; frame/image/video/audio views only when verified index exists. Add corpus ingestion/background jobs.

**P3 — Integrated Live.** Build camera UI using original components/design, port lifecycle guards, dual camera, overlays, timeline, mentor guidance and push-to-talk. Browser mock tests + manual physical camera checklist.

**P4 — Models & Routing studio.** UI form builder + YAML upload/editor/template/diff/apply/rollback/profiles; Laya/NVIDIA parallel, sequential/fallback, STT; safe synthetic tests and routing trace. Add per-session override.

**P5 — Durable storage and 12-hour backup.** Implement private GitHub backup repository workflow, consistent encrypted state snapshots, external media coverage manifests, retention/alerting and dry-run restore. Prove a `workflow_dispatch` backup and off-Space restore in a staging environment; do not claim success based on a local cron mock.

**P6 — HF staging deployment.** Build resource-fit Docker image, restore/backup strategy, remote provider smoke tests. Deploy to **private staging Space only with explicit approval**. Validate external browser access, authenticated session, both physical cameras, API/media paths and object storage durability.

**P7 — Controlled switch to `openweb`.** User visual approval using before/after screenshots; backup and rollback; switch only after tested staging sign-off. Preserve evidence.

### Required test matrix

- Backend functionality: `/api/videos`, details, `/api/search`, `/api/search/image` (supported/unsupported), `/api/ask`, `/api/stats`, experiments, media Range streaming, ingress/ingest states and errors.
- UI: original page screenshot diffs, keyboard/mobile access, no missing nav, video seek, cited segments, meaningful no-data state, Live visual consistency.
- Live: two distinct simulated streams, camera permission and contention, stop/dispose, stale-frame version checks, bounding-box overlay geometry/mirroring, combined observations, voice recording.
- Models: schema/SSRF/secret/security tests, parallel/fallback/partial success, synthetic tests, real Laya, real NVIDIA/Whisper only with actual credentials, embedding mismatch/version isolation, restore after restart.
- Backup: private repo, external 12-hour GitHub Actions schedule and manual dispatch, encrypted consistent snapshots, full scope/asset inventory, missed-run alert, real staging restore and retention.
- Deployment: Docker startup, one exposed port, no local inference weights, measured 2-vCPU/16GB resource use, private HF authentication, external persistence/backups and rollback.

### Done means

1. Original Video RAG UX remains recognizable and fully functional (screenshots approved).
2. The Library has useful content and a working upload-to-index pipeline or clearly seeded evaluation corpus.
3. Search and Ask return evidence-backed answers with timestamps and playable clips.
4. Dual-camera Live works from the **laptop browser**, independently and in parallel where hardware permits.
5. YAML routes can switch Laya, NVIDIA, both, or a configured VLM; security checks remain intact.
6. The private HF Space runs within its actual 2-vCPU / 16 GB allocation and operates without a DGX dependency.
7. Storage durability and private access are tested in the actual deployment, not just locally.
8. A **private GitHub backup repository** runs a verified backup every 12 hours (target), with encrypted snapshots, documented media coverage, alerts, and a successful clean restore test.
9. Source, docs, test reports, screenshots, rollout/rollback instructions and branch SHAs are delivered.

## 11. Explicit non-goals

- Replacing the original Video RAG frontend or making Models & Routing the homepage.
- Achieving an arbitrary ultra-small Docker/RSS metric at the cost of product quality.
- Claiming any NVIDIA API is a spatial detector/tracker absent proof, or claiming Laya outputs boxes.
- Running large local VLMs or Whisper on CPU Basic.
- Continuous 30fps external inference, uncontrolled API spend or unconsented recording.
- Launching Docker research subagents inside the HF Space during this UI/RAG restoration milestone.
- Modifying DGX, Needle router or unrelated inference infrastructure.
