# Visual Mentor v2 — release-readiness report

Reviewed 2026-10-17. **Development implementation ready for review; production
release remains blocked by external qualification and approvals.** No Hugging Face
Space or inference service was changed. No backup workflow was activated.

Application code commit: `baff0d78f04ee5782af53a059f4a2672e56a1a8f` on
`feature/video-rag-mentor-v2`, created from main
`7f8922cad8adb7e73a5f95ecfbf5b1a73e5bd46f`.
The prior feature branch stays at `245b686c916f0fcb0aff50b305e27f399c32910d`;
deployment branch was inspected at `c59fcf7495bbb6a59f45fd7e2f06c48e594547e1`.
Neither prior branch was merged wholesale or rewritten. The attached v2 spec
replaces the old spec only on this new branch.

## Implementation and audit outcome

| Area | Delivered | Qualification limit |
| --- | --- | --- |
| Original Video RAG UI | Main Library landing/cards, Search, Ask, experiments/charts, Architecture, details, timeline and clip modal retained | Original and current screenshot review awaits user approval |
| First launch | Immutable synthetic teaching clips, transcript keyword search and labeled evidence-extract answers | No production corpus or live embedding/LLM inference implied |
| Remote RAG | Model/dimension/preprocessing/segmentation/corpus identity, isolated revisions and atomic CURRENT switch; compatible vector reuse; finite/shape validation | Only text embeddings implemented; actual model credentials unavailable |
| Media ingestion | 64MiB/30min limit, SHA dedup, persisted single-worker queue, CPU proxy/keyframes, 30s segments, remote STT, versioned text indexing, retry/cancel/manual transcript | End-to-end provider steps mocked; real FFmpeg and SQLite executed |
| Live | Two independently selected local streams, device persistence/change handling, start/stop/consent, 1–2fps sampled transfers/backpressure, exact-still overlays, freeze/fullscreen/local photo, timeline, voice and advisory guidance | Simulated cameras only; physical device/permission/browser matrix outstanding |
| Routing studio | Native cards, route matrix/form, draft profile name, YAML import/editor/export/diff, validation-gated CAS apply/rollback, synthetic traces and session overrides | Live provider test status is not persisted as a readiness claim; conditional advanced predicates remain YAML-editable |
| Route execution | Single, fallback, parallel all/first-valid/quorum, typed sequential, conditional; failure isolation and provenance-preserving fusion | No fabricated Laya geometry; no calibrated semantic voting or general ensemble claim |
| Private access | User/admin bearer separation, private metadata/media, Secure HttpOnly media-only cookie, origin checks and no credential values in YAML/URLs | HF private gateway and actual external browser access not verified; shared roles, not per-person accounts |
| Provider egress | HTTPS allowlist, private/metadata IP and redirect denial, pinned direct DNS/SNI, sensitive destination rechecks, reserved infrastructure secret-reference denial | Trusted proxy must enforce public-only DNS/metadata policy in actual staging |
| Backups | Consistent SQLite online backup, strict config history, encrypted bounded archives, media inventory/independent checksums, isolated private-permission restore, stale monitor and conservative retention | Local proof only; separate private repository, durable publisher, Action and off-Space restore still blocked |
| HF package | Pinned CPU Docker, FFmpeg, supervised Next/FastAPI, one exposed port 7860, API/media rewrites and Range | Local qualification only; no HF upload or production switch |

The original design-system components and charts were retained. Old GPU-specific
Architecture/setup statements were corrected or moved into explicitly historical
research documentation. No local inference service is started by the cloud/dev
launchers. No arbitrary 200MiB optimization target is used.

## Test evidence (live, real local and mocked are separate)

- **96 backend tests passed**: strict YAML/security/contracts, lifecycle/stale/version
  guards, partial failures/fusion/routing strategies, session overrides, protected
  media cookie/Range, index compatibility/corruption, jobs, encrypted restore,
  concurrent SQLite snapshot, secret/camera exclusions, missing/corrupt assets,
  size limits, stale schedules and newest-restorable retention.
- **21 browser tests passed** in the final full-stack-enabled run: 20 use UI fixtures
  or simulated devices; one uses the actual Next→FastAPI sample endpoints with no
  HTTP mocks, verifies Library/detail/transcript seeking, search, Ask citations,
  playable media/Range and Experiments. This is real local integration with a
  synthetic corpus, not remote-provider inference.
- Before new features, **24 original main screenshots and clip interactions passed**.
  Current 28 screenshot baselines cover six original routes at 1440/1280/768/390px
  and Live/Models at desktop/mobile. [Comparison](v2-evidence/ui-comparison.html)
  and [UI review matrix](v2-ui-review.md).
- ESLint completed with zero errors (one unused Architecture variable warning);
  production Next build/TypeScript passed. The final Docker build also
  executes the production web build. One Starlette TestClient/httpx deprecation
  warning remains; it is not a runtime failure.
- **Real CPU FFmpeg** prepares a generated test clip, extracts remote-STT audio,
  segments and keyframes. Mocked STT/embedding responses produce a real versioned
  index and searchable timestamped API result. This does not verify Whisper/VLM
  deployment compatibility or answer quality.
- **Real age encryption/decryption and clean temporary restore** use disposable
  identities and a separate local asset-copy directory. SQLite integrity/content,
  media hashes, staging isolation and private filesystem permissions are checked.
  No GitHub Actions run, external storage availability or production recovery is
  inferred from this local test.

Evidence files: `v2-evidence/backend-tests.txt`, `browser-tests.txt`, `lint.txt`,
`build.txt`, `container.json`, `runtime.json`, `laya-live.json`.

| Provider | Current evidence | Not established |
| --- | --- | --- |
| Laya | Live health/ready/info and a generated 64×64 image; backend=laya-vision, model=thaitea/laya-vision, placeholder=false; actual adapter returned advisory noul result in **22.632s** | Physical camera scenes, accuracy/calibration, free-form captions, boxes, concurrency SLA, cost or authentication enforcement |
| NVIDIA detection gateway | Mock HTTP schema/correlation/geometry, mixed Laya+detector parallel execution, partial failure/fusion | Actual endpoint/model/credentials and native NVIDIA protocol compatibility |
| Whisper-compatible STT | Mock multipart protocol and real FFmpeg audio processing | Actual endpoint/model/credentials and live timestamp/latency quality |
| OpenAI embeddings | Mock finite/dimension/version checks and real local index pipeline | Actual endpoint/model/credentials, retrieval quality or MRL support |
| OpenAI VLM/reasoning | Mock bounded image/transcript requests and cited answers | Actual endpoint/model/credentials, usage, cost or answer quality |

A Laya authorization header was available through the runtime and sent without
logging its value, despite the configuration inventory not listing it. Other
provider endpoint/key variables were absent. No credentials were copied into
source, images, screenshots or evidence. [Contract details](providers.md).

## Known failures found and corrected during qualification

- Browser media cookie authentication originally failed due to cached request
  headers; fixed at the actual auth boundary and tested through both ASGI mount
  and production Next proxy, including byte ranges and no cookie auth for APIs.
- Sample comparison/Experiments handlers inherited FastAPI Query defaults on
  internal calls; the unmocked browser test exposed the 500. Internal calls now
  pass concrete values and API regression checks cover all sample comparisons.
- Invalid vector shapes/nonfinite data now fail explicitly before search.
- Placeholder model IDs cannot be enabled; all shipped templates start disabled.
- Imported profiles cannot reference reserved admin/infrastructure/recovery secrets.
- The workspace's VFS Docker build exhausted disk on redundant layers; obsolete
  task build cache was removed and assembly changed to avoid duplicating FFmpeg
  layers. No running inference containers/services were stopped.
- A simulated camera test exceeded its default 5-second startup wait under build
  load. Its media-startup wait is now 15 seconds; final suite passes without retries.

## Remaining release blockers

1. **Explicit private backup repository approval** is pending. Proposed separate
   repository `JsonLord/visual-mentor-backups`; reviewed templates and local bootstrap
   are prepared. No creation, credentials or scheduled activation occurred. Latest
   real private workflow success: **none**. Actual off-Space restore: **none**.
2. Select/budget/provision private durable state and media storage plus an immutable
   source snapshot publisher. Current app state is local until externally backed.
   Local Docker-volume recreation does not prove HF durability. Arrange trusted
   external backup-status refresh. Large vectors/media and Git history compaction
   need an approved retention/cost policy.
3. Run the private workflow manually, verify ciphertext committed remotely, validate
   independent media availability, demonstrate offline-key clean restore and failure/
   missed-run alerts before enabling the 12-hour schedule as an operational service.
   [Concrete installation/restore steps](backup-restore.md).
4. Supply approved NVIDIA, Whisper, embedding and VLM endpoints/model IDs/credentials;
   qualify actual adapters, upload→index→Search/Ask, provenance, latency and cost.
   Multimodal embedding adapters remain unavailable, not simulated by text vectors.
5. Complete physical laptop/USB dual-camera, browser/OS contention, device reconnect,
   microphone and real provider frame-to-overlay latency tests. Laya's observed
   22.6s synthetic latency is not a rapid-live-overlay SLA.
6. Approve private HF staging, inspect/backup existing openweb, verify actual
   anonymous rejection and authenticated roles, external egress, source revision,
   storage recovery and real 2-vCPU/16GB workloads. User UI approval must precede
   any production switch. No inaccessible Space screenshots/visibility are claimed.

## Exact next operational steps

[HF staging/deployment/rollback](deployment-hf.md) specifies approved staging repo,
source upload patterns, secrets/config, anonymous/authenticated checks, recreation,
visual approval and controlled rollback. [Backup/restore](backup-restore.md) specifies
private repository bootstrap, cron `17 0,12 * * *` UTC, external immutable-source
layout, scoped credentials, offline recovery keys, manual Action/restore evidence,
monitoring, retention and costs. Both activation paths require explicit approval.

## Final container measurements

Image `video-rag-mentor:v2-review`: **sha256:51259fc8221de63f5b4dfaf9e247e64e1496806ca88ca72f85ec243fae1ef1a3**; **860.5 MiB**.
Application code corresponds to the code commit identified above; later commits
contain evidence/runbooks and approval guards for the external backup templates.

- Resource probe startup **8.893s**; independent authentication/volume qualification
  startup **13.009s**. Both use **2 vCPU / 16GiB**, no GPU and network=none, with no
  published host ports. UID 1000; no local inference packages/model weights/devices.
- Idle application process RSS **179.6 MiB**; sampled application RSS peak **203.7 MiB**;
  cgroup peak **219.7 MiB**. RSS may count shared pages; cgroup measures the container.
- **180 successful HTTP requests**, p50 **9.97ms**, p95 **90.22ms**, alongside CPU FFmpeg
  transcoding of the generated 60s clip and 50 searches over a synthetic **10,000×768**
  normalized matrix. Combined in-process benchmark work **1.323s**. Aggregate workload
  CPU time **2.876 CPU-seconds** over **1.871s** wall time including measurement probes.
- Private media cookie and bearer Range requests, user/admin separation, forbidden
  origin rejection, CAS apply/rollback and state recovery after recreating the
  container passed. Local Docker-volume recovery is not HF durability proof.

These measurements exercise a small synthetic corpus and synthetic vector math,
not real dual-camera/provider traffic, production retrieval quality, large video
imports, long-duration capacity or provider costs. Actual provider/physical-camera
frame-to-overlay p50/p95 and deployment load remain staging gates. No provider
price was supplied; costs are unverified rather than estimated from invented rates.
