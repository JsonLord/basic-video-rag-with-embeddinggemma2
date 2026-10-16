# Visual Mentor release-readiness review

Reviewed 2026-10-16 (Europe/Berlin). Branch: `feature/visual-mentor`. Requested baseline: `4549ff5906a3b9e32f4a42899f4fc75a56fe8e52`. Reviewed application/build source: `2d8e4b6182fc3ea4c8d3779f194911ceab4d76a9`; the following report commit contains evidence/documentation only.

## Verdict

**Qualified as a CPU-only private staging candidate; not full hybrid production sign-off.** The pinned container starts offline, runs without a local AI stack, enforces application authorization, and restores configuration from a Docker volume. Laya has passed a real synthetic-image call through the application adapter. The remaining provider, hardware and HF deployment gates below must be closed before claiming the full specification is satisfied.

No HF Space was created, pushed, changed or published. No DGX services or inference infrastructure were changed or restarted. Only this checkout's development application was restarted on its existing ports. Qualification containers published no host ports.

## Audit against spec.md and prior reports

| Requirement | Outcome and limit |
| --- | --- |
| CPU runtime, no AI models | PASS in final image: network disabled, no GPU devices, prohibited packages/weights absent, lightweight health and explicit unavailable-inference response |
| One public origin/port | PASS locally: Next standalone proxies API/media to loopback FastAPI; image exposes 7860 only; no host ports published by qualification |
| Library, search, Ask, media | PASS with temporary corpus and mocked inference, including citations/keyframes and Range playback. Real corpus/provider quality unverified |
| Dual camera | PASS in simulated-browser tests for selections, distinct streams, consent, contention, stop/revocation/teardown, stale results and mirror/resize. Physical laptop+USB acceptance still manual |
| YAML/routing | PASS for schema, role/capability checks, safe parsing, snapshots, parallel/partial failures/fusion, timeout/cancellation/fallback, apply/rollback/version conflict and backups |
| Laya/Jev | Source verified and real synthetic gateway/application-adapter calls passed. Wrong backend/model, placeholder and malformed answers rejected |
| NVIDIA, Whisper, OpenAI embeddings/vision | Mock contracts/configuration passed; real endpoint URLs, credentials, support and output quality remain unverified |
| Auth/privacy | Real-container bearer role/origin checks passed. Camera/audio privacy and SSRF/redirect/fallback guards covered by tests. HF's private outer gate remains untested |
| Persistence | Local Docker volume survived container removal/recreation at revision 4. Actual HF persistent mount/rebuild survival not established |
| HF deployment configuration | Prepared: pinned Dockerfile, README Space metadata, env names, profiles, secrets/storage guide, exact approval-gated procedure. Not deployed |

[docs/validation.md](validation.md) remains historical evidence for 4549ff5. Its former Laya blocker is superseded by the source discovery and live evidence below. Earlier mocked results have not been promoted to live results.

## Defects fixed

- **Capture lifecycle:** session authorization remounted cameras and reset selected device IDs. Selections now survive authorization; late permission grants stop their returned tracks after teardown. Hidden pages, recorder errors and permission loss stop microphone capture and discard/abort transfer. Audio destinations are displayed and duration reflects elapsed recording time.
- **Stale observations:** camera/frame/request matching omitted configuration revision, image dimensions and browser-side box bounds. All must now match before timeline/overlay updates. Wrong frame/config/dimensions/boxes and delayed results after stop have regression tests.
- **Partial provider failures:** malformed detector objects could escape as exceptions and fail a parallel route. They now produce isolated invalid_output results while preserving other valid boxes/decisions. Malformed URLs and invalid/overflowing embedding vectors fail safely.
- **Configuration correctness:** schemas reject inconsistent capabilities, wrong feature providers, mixed embedding identities and invalid condition types. Disabled optional providers do not need live endpoint variables merely to save a profile. Circuit state now follows provider/model/endpoint configuration instead of blocking a replacement provider.
- **Laya contract:** replaced the unavailable stub using immutable source and captured live evidence. Requests use bare imageBase64 JSON; two evidenced response forms are accepted. Non-generative scores remain advisory decisions, never spatial boxes, generated prose or autonomous actions.
- **Destination security:** direct HTTPS pins a validated public IP while retaining Host/TLS SNI. The inherited trusted proxy route remains in use, including proxy DNS if local resolution is unavailable. Literal/private resolved destinations and redirects remain denied. Proxies must enforce public-only resolution at connect time; see the remaining boundary below.
- **Authorization/redaction:** an explicit origin allowlist now takes precedence over forwarded host. Framework validation errors no longer echo private images/task text or pasted credentials. Non-finite timestamps return safe 422 errors instead of a possible JSON serialization 500.
- **Expiry/persistence:** expired observations/speech are reaped on access and by a 30-second cleanup loop. Session mutations share one event loop. Config updates preserve previous committed history before atomic switching and directory fsync. Use one API worker with this file store.
- **Packaging:** reviewed Node/Python base digests are pinned; nested .env/PEM files are excluded from every build stage. Build proxy configuration and registry credentials were preserved; CA mounts remain temporary and TLS/hash/signature checks enabled.

These are fixes and qualification tooling for existing capabilities. No autonomous agent, research service, inference infrastructure change or additional public port was added.

## Final executed evidence

| Check | Actual outcome |
| --- | --- |
| Python tests | **77 passed**, no skipped tests; one Starlette TestClient/httpx deprecation warning |
| Frontend lint | passed |
| Frontend production build | passed, including TypeScript and standalone output |
| Playwright / system Chromium | **12 passed (11.7 seconds)**; simulated devices, mocked application inference responses |
| Pinned Docker build | passed, no host networking, verification enabled |
| Offline container qualification | passed: network=none, 2 CPU/1 GiB, uid 1000, no published host ports |
| Real-container application auth | missing user denied; user denied on every admin configuration/test/dry-run path; forged origin/forwarded host denied; authenticated admin apply/rollback succeeds; config export contains no tokens |
| Persistence | remove/recreate with a dedicated temporary Docker volume restored profile and revision 4 |
| Model/GPU inspection | no GPU devices, torch/torchvision/torchaudio/torchcodec/transformers/sentence_transformers/vllm/Whisper/ONNX runtime/HF Hub packages or model weight files found |
| Functional HTTP workload | **180 requests passed** across UI/library/stats/health/OpenAPI; these were not inference requests |
| Whitespace check | git diff --check passed |

Mock wire tests cover remote Whisper multipart, OpenAI chat/vision and embeddings, detector frame/dimensions/boxes, Laya source/live answer envelopes, simultaneous Laya+NVIDIA adapter calls, either provider timing out, malformed partial output, placeholder rejection and sensitive fallback denial. Typed fusion preserves detector boxes and Laya scores separately with provenance; it does not infer object association/tracking or manufacture coordinates.

Browser tests verify selected device constraints and two distinct **synthetic** streams. They do not prove two different physical devices work. Additional tests cover permission denial, device contention, track end, late permission resolution after navigation, stale/invalid observations, delayed result discard, mirror/resize geometry, microphone hide/error teardown and YAML apply. Live provider replies are mocked in these browser tests.

## Live Laya investigation

Reference source: [JsonLord/laya-inference, 77b324ac6c72efee883c41fd333e84007c55bed0](https://github.com/JsonLord/laya-inference/tree/77b324ac6c72efee883c41fd333e84007c55bed0), especially middleware/validation.ts, utils/router.ts, routes/systemOne.ts and layaVisionService.ts. It was retrieved read-only through existing Git access after the user supplied the repository. The HF source API was inaccessible.

- GET /health, /ready and /v1/info on https://leon4gr45-needle-router.hf.space returned 200. Ready reports placeholder=false; metadata identifies thaitea/laya-vision. /openapi.json and /docs remain 404.
- The reference source contains a placeholder vision implementation and an older flat response. It establishes the request fields, not the deployed model's authenticity. JSON uses state + typed questions + **imageBase64 without a data URI**; top-level JSON image is not this protocol. Multipart was not used.
- A direct synthetic 64×64 PNG request returned backend laya-vision, model thaitea/laya-vision and checkpoint f2fe3c12cb6d04c59d8a190250bf3fb40fc828dc. Its raw response is preserved in tests/fixtures/laya-live-synthetic.json. The deployed source revision remains unknown.
- A separate generated JPEG request passed through Visual Mentor's real adapter in **8.002 seconds**. See [laya-live.json](release-evidence/laya-live.json). Neither call used a camera, personal media or an API key.
- The source envelope is results.<question>; the deployed gateway returns results.answers.<question> with provenance. Both evidenced variants are tested. Other/placeholder/wrong-model responses fail closed.
- The adapter exposes one fixed noul inspectability question. It does not claim to expose upstream choice/score editing, task-specific classifiers, scene captions, object boxes, tracking or generative mentoring. Scores are advisory and no automatic action is taken.
- These results establish a working HTTP contract and the receiver's reported non-placeholder provenance, **not** an independent model-weight audit, accuracy benchmark or privacy/retention guarantee. Remote PyTorch metadata describes the external router, not packages in the Visual Mentor image.
- The gateway accepted synthetic inference unauthenticated. Do not assume that configuring a client key enforces authentication at that receiver. If the endpoint requires a key later, provision LAYA_API_KEY securely and add its reference to the selected provider.
- Local DNS was unavailable in this managed environment. The configured trusted HTTP proxy supplied resolution. No network-policy bypass, route change, private-network grant or insecure TLS setting was used.

## Final container measurements

Image: `sha256:c11dfb41dacf54877d1255cf6fb293922473d0f030dc9ae1429bb01a9f4a7a2a`.

| Metric | Actual |
| --- | --- |
| Uncompressed image | 441,984,679 bytes / 421.5 MiB |
| Startup to proxied health | 6.749 seconds |
| Offline qualification startup | 8.029 seconds |
| Idle aggregate app RSS | 176.4 MiB |
| Sampled peak aggregate app RSS | 203.9 MiB |
| Cgroup memory peak | 140.1 MiB |

The exact image was used by both qualification and resource scripts. Raw evidence: [container.json](release-evidence/container.json), [runtime.json](release-evidence/runtime.json). Aggregate RSS sums application processes and may double-count shared pages. Sampling is every 25 ms plus idle/post-workload snapshots; it is not an exact instantaneous peak. Cgroup accounting differs. These values meet the <500 MB idle/<1 GB peak targets for the tested HTTP workload only. Real dual-camera/audio/provider/corpus load remains unmeasured.

## Remaining release gates

1. **Actual private HF target and approval:** select a new Visual Mentor application Space, obtain deployment approval, provision Private visibility/HTTPS and distinct app tokens securely. Confirm anonymous app/API/media access is denied by HF. No deployment credential or new target was configured here. Do not overwrite the needle-router inference Space.
2. **Real providers:** supply exact NVIDIA gateway, Whisper, VLM and embedding endpoints/model IDs/capabilities and secure key bindings as needed. Their variables were absent during review. Keep unverified optional routes disabled. A generic detection-http fixture is not a verified NVIDIA service; full live Laya+NVIDIA fusion is not established by the mocked hybrid tests.
3. **Real laptop+USB/browser acceptance:** verify simultaneous physical devices, switching/contention/revocation, mirror/portrait/resize, explicit opt-in and slow-inference backpressure, navigation/hide teardown and microphone support. HF's iframe must delegate camera/microphone; use the direct HTTPS app origin if needed.
4. **Processor/egress/privacy approval:** approve actual camera/audio destinations and retention policies. Direct connects enforce public IP pinning; configured proxies must independently block private/metadata destinations at resolution/connect time. The app cannot certify the proxy's network policy. Public Laya reachability is not such approval.
5. **HF storage and load:** verify uid-1000 persistent storage, config/library survival through the actual Space restart/rebuild, and memory/latency with representative index/provider traffic. A local Docker volume is not HF persistence evidence.

## Exact deployment steps

The complete commands, variables, secure provisioning, approval-gated Git push and post-deployment checks are in [deployment-hf.md](deployment-hf.md), section **Exact release procedure**. [providers.md](providers.md) documents the actual Laya and explicit detection-gateway contracts. [security.md](security.md) records single-user and trusted-proxy assumptions.

In order: approve a new private Docker Space; configure distinct application Secrets and only selected provider Secrets; set the exact application origin/provider hostname allowlists and endpoint variables; configure persistent paths if needed; approve then push the reviewed final commit; check private HF access controls and internal health; validate/apply the chosen YAML profile; run synthetic provider tests; complete the physical-camera/privacy/load gates. None of those publication steps was performed during review.

Reproduce locally without exposing host ports:

```bash
/workspace/visual-mentor-venv/bin/python -m pytest -q
npm --prefix web run lint
npm --prefix web run build
# Run browser tests against the started existing application on 7860:
(cd web && CHROMIUM_PATH=/usr/bin/chromium npx playwright test)
# From the repository root:
/workspace/visual-mentor-venv/bin/python scripts/qualify-release.py --image visual-mentor:release-review
VM_RUNTIME_IMAGE=visual-mentor:release-review /workspace/visual-mentor-venv/bin/python scripts/measure-runtime.py
```

The qualifier creates/removes only its uniquely named temporary containers/volume. The build uses the supported proxy and a read-only CA secret as documented; no infrastructure restart is needed. Metadata-only Laya preflight is available via scripts/check-laya.py; --synthetic explicitly sends one generated image for inference.

## Review commits

```
2344f12 fix: qualify CPU deployment, Laya contract, routing and capture privacy
7810023 fix: redact private inputs from request validation errors
5b0da38 build: pin reviewed Node and Python base image digests
2d8e4b6 build: exclude nested local credential files from Docker context
```

The final report/evidence commit follows these source changes. Its full SHA is provided in the review response and obtainable with git rev-parse HEAD.
