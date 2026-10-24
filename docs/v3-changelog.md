# Visual Mentor v3 implementation changelog

## Gate 00 / Gate 01 — 23 October 2026

- Captured exact source SHA and original backend/browser baseline in an isolated
  branch; preserved original Video RAG navigation, pages and fixtures.
- Added independent local camera recorders with optional separate microphone consent,
  codec negotiation, pause/resume, bounded RAM/time, playback, download and deletion.
- Added authenticated, explicit recording import using the existing ingestion/jobs
  pipeline, with upload progress/cancel and terminal indexing status.
- Fixed missing-duration streaming WebM ingestion using a bounded seekable proxy;
  added real FFmpeg tests for streaming input and over-limit rejection.
- Added typed source-aware spatial association, persistent track selection, missing/
  reacquired state, mirror-safe crop geometry and separately labeled canvas output.
- Added margin/minimum crop/smoothing/lost-timeout/reset/fullscreen/annotation controls.
- Hardened hydration and Next Activity navigation cleanup for camera/encoder/mic/
  pending permission/blob resources; originals remain independent of recorders.
- Added native Chromium simulated dual-camera tests, consent/quota/lifecycle tests,
  geometry fixtures and a real local recording-to-Library/index/playback integration.
- Added a disabled v1 candidate profile, architecture/qualification report and raw
  evidence. Full v3 conversation, ASR, A2A and native NVIDIA qualification remain open.
- No production deployment, external provider activation, backup runtime migration,
  inference infrastructure change or recurring schedule activation.


## Gate 02 and Gate 03 foundation — 23 October 2026

- Added distinct strict configuration v2, explicit migration preview and preserved
  raw v1 history objects, mixed-version restart, CAS, protected export and rollback.
- Updated only encrypted configuration validators for mixed schemas; proved real
  encrypted history/SQLite-ledger recovery using mocked GitHub storage.
- Added exact HF OPENAI_COMPATIBLE_* / A2A_* defaults to the existing registry,
  sanitized studio metadata, explicit roles and four disabled v2 presets.
- Added conservative duplicate-detection fusion with contributor evidence and
  capture/history/session revision correlation; delayed changes fail closed.
- Gate 02 passed 144 backend and 42 browser cases, lint and production build.
- Began Gate 03 only after acceptance: bounded OpenAI SSE, complete typed tool-call
  validation, authenticated/privacy-checked registry and durable idempotency in
  existing jobs.sqlite. Full conversation orchestration/UI and real A2A remain open.
- Backend total after the foundation: 159 passed, no skips. No live model, Docker,
  infrastructure, workflow, deployment or production recovery claim was added.
