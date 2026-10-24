# Visual Mentor v3 qualification — 24 October 2026

**Decision: Gates 02, 03 and 05 have fixture-qualified implementations. NO-GO for production deployment or live Qwen/A2A claims.**

Latest continuation starts from `9e31e867669519cd985562ce63487d760cba6a0d`; see
[v3-gate03-report.md](v3-gate03-report.md) and [v3-gate05-report.md](v3-gate05-report.md) for the completed conversation/research paths. Historical Gate 02 starting point was `7c2c1a87164d94a49105f374580703ff61e7bf1c`; see
[v3-gate02-report.md](v3-gate02-report.md) for migration, precedence, exact evidence
and the remaining work. Earlier Gate 01 evidence below remains preserved.
This is an incremental implementation, not completion of spec.md. No deployment,
production inference, backup checkpoint, recurring workflow or remote infrastructure
was changed. Existing credential/deployment reports and their evidence are preserved.

Source: `feature/video-rag-mentor-v2` at
`64c97fe59f6b7aafdd6298488a3e185bd3bfa43d`.
Implementation: `feature/visual-mentor-v3-live` in an isolated worktree.
Use `git rev-parse HEAD` for this report's enclosing commit; PR/final delivery records
the final SHA separately to avoid a self-referential commit hash.

## Gate status

| Gate | Result | Evidence / remaining work |
| --- | --- | --- |
| 00 audit | PASS | Exact source object verification, v2 backend/browser baseline and spec/contracts audit in v3-baseline.md |
| 01 browser recording/framing acceptance | PASS, simulated devices | Independent native encoding, review/export/delete, pause/resume, microphone and import consent, byte/time limits, lifecycle cleanup, typed spatial association and smoothed selection; actual authenticated import to Library/Search/playback |
| 02 provider/config extension | PASS, synthetic contracts | Separate strict v2 migration, preserved v1 history/CAS/export/rollback/encrypted restore, HF defaults/studio switching and correlated routing. Native NVIDIA remains unqualified; target selection stays reserved and examples remain disabled |
| 03 conversation | PASS, fixtures/local integration | Durable owned API/SSE/UI, complete correlated tool continuations, grounded index/scene tools, bounded idempotency and cancellation; live model unqualified |
| 04 optional Phonon | NOT IMPLEMENTED | No mandatory dependency/weights added; pinned engine/license, English fixture and actual 2-vCPU measurements still required |
| 05 A2A research | PASS, official SDK fixtures/local integration | Durable async submit/poll/cancel, restart reconciliation and structured evidence; live agent key/network qualification pending |
| 06 live integration | BLOCKED externally; diagnostics/local regression PASS | Qwen/A2A credentials missing, native NVIDIA endpoint unknown, Docker CDN Forbidden; see v3-gate06-report.md |
| 06 release | PARTIAL / BLOCKED | Production Next build/lint/backend/browser pass; CPU Docker build blocked at registry proxy policy. Physical devices and live/private deployment gates unrun |

The broader v3 UX still needs PiP/composite outputs and clickable object selection;
keyboard object selection and separately labeled original/canvas recording exist.
Associations use sampled detections, not frame-rate motion tracking. There is no
claim of live NVIDIA/Laya/Qwen/A2A, Phonon or production backup recovery success.

## Actual checks

| Command/check | Observed outcome | Kind |
| --- | --- | --- |
| Baseline Python pytest | 106 passed, 14 skipped | Local backend; age-dependent skips |
| Baseline Playwright | 22 passed, 1 skipped | Simulated devices / mock HTTP; fullstack opt-in absent |
| Python pytest before test-tool installation | 110 passed, 14 skipped | Local backend, age absent |
| Gate 01 Python pytest with verified age | 124 passed, no skips, one existing Starlette warning | Local backend, real FFmpeg/age; mocked provider/GitHub transports |
| Existing config/Laya/security subset | 41 passed | Mock transport, not provider integration |
| Gate 01 Playwright with both integration flags | 38 passed in 1.2m | Native browser encoding and real local HTTP/media/index; synthetic camera/mic and inference fixtures |
| npm --prefix web run lint | 0 errors, one existing Architecture unused-variable warning | Static analysis |
| npm --prefix web run build | PASS | Production Next.js / TypeScript build |
| Gate 02 backend / browser | 144 / 42 passed | Real local execution with synthetic external transports |
| Gate 03 foundation + full backend | 159 passed, no skips | 13 new streaming/tool tests including real age recovery; no live Qwen/A2A |
| CPU Docker build | BLOCKED | Managed daemon available; registry-1.docker.io manifest HEAD returns proxy Forbidden |

Raw output is in `docs/v3-evidence/`. Browser tests include all existing UI screenshot
regressions at four sizes. Only the two deliberately changed Live screenshots were
updated; original page and Models snapshots were preserved. Initial failed runs
identified early-hydration clicks, retained hidden routes and overly broad video
selectors. Media controls now wait for hydration; Activity cleanup clears tracks,
clip state and blob URLs. Tests wait for navigation and select visible media.

The ingestion test uses Chromium MediaRecorder output (VP9/Opus), not a hand-built
mock Blob. It exercises authenticated /api/ingest, real FFmpeg/ffprobe, jobs.sqlite,
versioned embeddings files, original Library navigation, playback and Search.
The transcript and 3-dimensional embeddings come from a deterministic in-process
adapter, **not** Whisper/OpenAI. `recording-ingestion.json` contains a complete
job, source duration-header result, index revision and SHA-256/size for media,
metadata/transcript/index artifacts. The disposable fixture held multiple sequential
test captures; no real user media or production library was used.

Separate MP4 and non-seekable WebM backend tests exercise successful ingestion and
provider-failure recovery. A reduced-duration limit fixture verifies neither proxy
nor index is published when a streaming capture exceeds the allowed duration.
Initially 14 tests skipped because age/age-keygen were absent. The official age v1.3.2 Linux AMD64 archive was then installed only under /tmp for tests; its SHA-256 `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10` matched the GitHub-published asset digest. All 124 tests then passed with real encryption/local recovery and mock GitHub storage. This is not a live GitHub recovery pass.
No live GitHub release upload or off-Space destructive recovery was attempted in this v3 task.

## Reproduce local checks

Use the existing frozen venv and web dependencies, FFmpeg and Chromium.
For all 124 backend cases, install a verified age/age-keygen and put them on PATH
(or set AGE_BIN and place sibling age-keygen on PATH). This run used
`AGE_BIN=/tmp/v3-age-v1.3.2/age/age` and prepended that directory to PATH. Do not use
a production state directory. From the implementation worktree root:

```bash
VM_BACKUP_ENABLED=false VRAG_DATA=/tmp/v3-pytest/data VM_STATE_DIR=/tmp/v3-pytest/state \
  /workspace/visual-mentor-venv/bin/python -m pytest -q
npm --prefix web run lint
npm --prefix web run build
```

For all 38 browser tests, first start this **test-only** backend in a separate
terminal. It refuses startup without opt-in and a disposable `/tmp/v3-` data path;
never deploy it. Only the inference adapter is mocked, and backups are disabled.
Choose a new directory for a clean repeat. Use the existing loopback port only if
free; do not stop an unrelated listener.

```bash
PYTHONPATH=.:tests VM_V3_FIXTURE=true VM_BACKUP_ENABLED=false \
  VRAG_DATA=/tmp/v3-browser-repeat/data VM_STATE_DIR=/tmp/v3-browser-repeat/state \
  /workspace/visual-mentor-venv/bin/python -m uvicorn v3_fixture_server:app \
    --host 127.0.0.1 --port 8000
```

From `web/`, in another terminal:

```bash
VM_FULLSTACK=1 VM_RECORDING_FULLSTACK=1 CHROMIUM_PATH=/usr/bin/chromium \
  npx --no-install playwright test
```

Playwright starts or reuses the loopback dev frontend on 7860. Running without the
two flags intentionally skips those integrations. The fixture uses an explicitly
synthetic test credential contained in the test; never replace it with a production
secret. Stop only your fixture process when done.

## Resources and external blockers

No new 2-vCPU CPU/RSS, physical-camera FPS, latency p50/p95, provider cost or Phonon
benchmark was measured. Test runtimes are not inference performance. Configured
limits: two independent 128 MiB local clips (256 MiB total plus encoder/blob overhead),
one encoder and optional mic per camera, 64 MiB server import, 30-minute wall limit,
15 fps canvas capture request, at most 64 detections/update and 128 retained tracks.
Actual browser memory can exceed encoded blob sizes. Existing v2 resource figures
are historical and do not qualify this branch.

The Docker daemon health check passed (28.4.0), but a clean build cannot resolve the
pinned Node base image through current policy. No TLS/proxy bypass, daemon restart,
new port or replacement base image was used. Buildx's writable local cache was
moved to /tmp while preserving Docker credentials/context restrictions.
A saved environment draft preserves existing hosts and adds registry-1.docker.io,
auth.docker.io, deb.debian.org and security.debian.org. Review/save/publish is required;
additional exact redirect hosts may need diagnosis after the manifest request works.
Saving the draft is not evidence a container build or startup passed.

Existing private HF authentication, GitHub upload-host credential/recovery, actual
NVIDIA/STT/embedding providers and physical integrated+USB camera qualification
remain gated as recorded in v2 reports. This branch does not activate or repair those
external systems. Further implementation of Gates 02–05 can continue with fixtures;
it is not dependent on production deployment permission.

## Next gate and activation boundary

Gate 02 acceptance now passes. Continue Gate 03's authenticated conversation API/UI,
durable turns, bounded context and grounded retrieval/scene handlers using the
stream/tool boundary. Keep real A2A dispatch off until Gate 05's official SDK and
reconciliation qualification. Optional Phonon remains Gate 04 work.

After code completeness, rerun CPU Docker, perform a private auth/provider/resource
qualification and a recovery drill. Deployment and production schedule activation
still need explicit approval. A draft PR does not authorize those actions.


## Reviewable implementation commits

- `1dea8750e5d3414786c27ab26927ef1598594c0e`: exact source audit and baseline.
- `39af3896046dceae48aa3e8fa76c8af7983f4840`: bounded streaming WebM ingestion fix/tests.
- `54d2c70bb974f0fb743c923193e886d20885f4ef`: browser recorder/framing/lifecycle and integration tests.
- The enclosing documentation commit adds qualification logs, disabled profile,
  architecture and changelog. Final delivered HEAD is recorded in the draft PR.


## Gate 03 / 05 completion evidence

The new reports supersede the earlier “foundation/pending” next-step descriptions
above. Gates 03 and 05 run end to end with actual authenticated local API, SQLite,
FFmpeg/index/clip playback, browser streaming, official A2A SDK and synthetic remote
protocol fixtures. No live Qwen/A2A success is claimed. Final counts/logs are in
`v3-evidence/gate03-complete/` and `v3-evidence/gate05/qualification.json`.
The initial full browser regression log is preserved separately: it found an idle
chat authentication alert affecting camera-only flows. The panel now waits for a
configured session token before loading history; the camera suite was rerun.

A new interpreter reconciles a persisted remote task without another submit. Real
age encryption plus destructive local restore preserves conversation messages,
research remote identities and the idempotency ledger through existing jobs.sqlite
coverage. GitHub is mocked in this test; this is not a live repository recovery.
The browser full loop keeps both simulated camera streams alive during research,
uses an actually ingested/indexed clip, explicitly incorporates completed evidence,
and reloads the durable history. Only intended Live snapshots change.

The A2A cloud draft was saved with the selected host, URL template and missing
secure token requirement. Saving did not apply/publish it. Add the token securely,
review/save/publish the environment and include the host in VM_ALLOWED_HOSTS.
Then run the read-only `scripts/qualify-a2a.py` probe. Full live remote research
requires subsequent reviewed lifecycle qualification, not just card discovery.
The actual task process currently has no A2A or OPENAI_COMPATIBLE credentials.

A fresh base-only `uv sync --frozen --no-dev` installation and API/SDK import passed,
without Torch/Transformers/vLLM. The runtime hashed lock was regenerated; the main
lock preserves legacy optional package pins. A full optional-graph resolver attempt
was denied at the PyTorch index, so SDK additions were resolved in a base-only
project constrained to the old pins, merged with the untouched legacy blocks, and
verified with `uv lock --check --offline` plus the real frozen installation.
No optional GPU package or model was downloaded.

CPU Docker remains BLOCKED by the historical registry policy denial. Private HF,
physical devices, real provider inference/cost/resource qualification and production
backup recovery remain outstanding. Production deployment and recurring workflow
activation remain unauthorized. Optional Phonon stays separate/off.

Final completion acceptance: **175 backend tests passed, zero skips; 43 browser
tests passed; production Next build passed; lint zero errors and one existing
Architecture warning.** The added speech review/citation playback integration also
passed independently. Initial browser and test-type build failures are retained
separately with the final successful logs.

Implementation checkpoints:
- Backend/SDK/tool lifecycle: `fae817c062c84f85fd82b1e835604d67020da2f4`.
- Live conversation/speech/research UI: `bd0a6339b1280ef2ddaafc176d37de41f309aecd`.
- The enclosing report commit is recorded by full SHA in Draft PR #3 and delivery.


## Gate 06 integration qualification — 24 October 2026

Starting SHA `75085f80e657ac5150951ab94d21192833049b8e`. The standalone Qwen
qualifier, typed-probe/state isolation fix, compiled frontend secret scan and
additional HF/A2A/framing tests are implemented. Final regression: **191 backend
passed, zero skips; 44 browser passed; Next production build passed; lint zero
errors and one existing warning.** No Gate 06 screenshot baseline changed.

Live Qwen and A2A remain BLOCKED_CREDENTIALS. No live research was authorized or
submitted. NVIDIA source review identified a native NV-Grounding-DINO candidate,
not a deployed compatible endpoint; custom detection-http remains intact. Docker
was actually retried and now fails Forbidden at production.cloudfront.docker.com
while resolving the pinned Node base, beyond the prior manifest-only blocker.
Container startup, RAM/CPU, native inference latency and resource p50/p95 remain
unmeasured; imports/test runtimes are not substitutes. Phonon-2 source/licensing/CPU
feasibility was reviewed without installing or downloading weights.

The Next build used five synthetic server-secret canaries; 26 compiled browser
assets (1,361,945 bytes) contained none. This is scoped build evidence, not live HF
or Docker qualification. All prior implementation/evidence is preserved. Gate 06
reports: [v3-gate06-report.md](v3-gate06-report.md),
[live-provider-qualification.md](live-provider-qualification.md),
[hf-production-checklist.md](hf-production-checklist.md),
[v3-nvidia-adapter-decision.md](v3-nvidia-adapter-decision.md), and
[v3-phonon-feasibility.md](v3-phonon-feasibility.md). Raw/machine-readable evidence
is under v3-evidence/gate06/. No environment publication, Space/inference service
change, production credential mutation or backup activation occurred.
