# Visual Mentor v3 baseline — 22 October 2026

Source branch: `feature/video-rag-mentor-v2`, exact fetched HEAD
`64c97fe59f6b7aafdd6298488a3e185bd3bfa43d`. Isolated implementation branch:
`feature/visual-mentor-v3-live` at `/workspace/visual-mentor-v3-live`.
The original checkout stays on its original branch/commit. No main reset/merge,
deployment, provider call, credential change or backup activation occurred.

## Source verification

The republished environment restored execution but dropped the wildcard host rule.
Native HTTPS Git fetch to github.com returned a proxy 403. The approved GitHub Git
Database API on api.github.com returned the source ref and objects. Three trees,
two blobs and two commits were retrieved; complete Git object SHA-1 values were
verified before accepting them. Public date-zone formatting lost by the JSON API
was reconstructed only when its complete commit hash matched exactly. No network
control, TLS or proxy authentication was bypassed. The two source commits change
only spec.md and the verbatim v2 archive; application code remains the tested v2.
A supported draft adds explicit Git/package destinations for ordinary fetch/push.

Read spec.md in full, docs/spec-v2-archive.md, v2 release/UI baseline, provider
contracts, deployment, backup and migration reports, the source inventory and
existing tests. `docs/security.md` referenced by old startup guidance is absent;
current security behavior lives in schema, egress, mentor API and security tests.

## Existing implementations and gaps

| Area | Current baseline | Planned extension / risk |
| --- | --- | --- |
| Video RAG UI | Original Library/Search/Ask/Experiments/Architecture, detail/citations/Range, synthetic sample | Preserve all original route components and screenshot fixtures |
| Live | Independent device streams, stop/hidden-tab teardown, consent, backpressure, exact-frame correlation, still overlays | Add opt-in local recordings without duplicating camera capture; test interrupted permissions and device loss |
| Tracking/framing | No browser association or stable local IDs; optional upstream IDs only | Typed deterministic same-camera/source/label IoU association; lost/reacquired state; aspect-safe smoothed crop; no Laya boxes |
| Recording/import | No live video recorder; existing authenticated 64MiB/30min ingestion and persistent jobs | Independent original/canvas recorders, bounded local blobs, replay/export/delete and explicit reuse of /api/ingest |
| Configuration | Strict v1 YAML, safe parsing, version CAS/history/rollback, provider env references | Gate 01 keeps schema unchanged; future v2 migration must preserve v1 readability/rollback rather than silently adding fields |
| Providers | Custom detection-http /detect; real narrow historical Laya noul test; remote chat/embeddings/STT | No invented NVIDIA native protocol, tracker API, Qwen endpoint, alias or model installation |
| Conversation/research | Advisory guidance only; research Protocol stub | Separate subsequent gates: streamed typed tools and official A2A SDK with durable outbound reconciliation |
| ASR | Remote OpenAI-compatible transcription; default contains no local model weights | Phonon optional and off by default; source/license/CPU benchmark not yet qualified |
| Backup | Encrypted GitHub release/checkpoint runtime and protected administration; upload auth blocked historically | No changes to backup runtime or scheduled activation; explicit imports enter existing backup scope normally |
| Security/runtime | User/admin scopes, explicit frame transfer, HTTPS destination restrictions, single public app port | Keep consent boundaries, reject stale observations, stop tracks/encoders/uploads on lifecycle changes |

## Initial actual validation

`VRAG_DATA=/tmp/v3-baseline-data VM_STATE_DIR=/tmp/v3-baseline-state
/workspace/visual-mentor-venv/bin/python -m pytest -q`: **106 passed, 14 skipped**,
one existing Starlette deprecation warning. The age/age-keygen tools are absent;
these encryption tests are skipped, not reported as passing. Raw log:
`docs/v3-evidence/baseline-backend.txt`. Browser baseline is recorded separately.

Installed prerequisites: existing frozen Python runtime, Node/Next/React dependencies,
FFmpeg and Chromium. A local dependency symlink reuses existing node_modules; no
lockfile/runtime dependency or production service is changed. New browser tests use
simulated devices and deterministic provider fixtures, never live user media.

## Implementation order

Gate 01 first: pure typed tracker/framing geometry; local recorder lifecycle with
separate camera/microphone/upload consents and hard byte/time quotas; canvas outputs
explicitly labeled versus original stream; preview selection and tracking IDs;
unit geometry and simulated-camera Playwright tests plus original UI regressions.
Only after those pass consider Gate 02+; do not claim Qwen, Phonon, native NVIDIA
or A2A qualification from fixtures. Stop before unsafe external infrastructure or
missing protocol assumptions. Existing backup/private-HF blockers remain visible.
