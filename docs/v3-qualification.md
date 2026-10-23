# Visual Mentor v3 qualification — 23 October 2026

**Decision: GO for draft review of Gate 00 / Gate 01; NO-GO for full v3 release or deployment.**
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
| 02 provider/config extension | PARTIAL | Existing v1 history/CAS/rollback and Laya+custom detector mock contracts pass; disabled v1 v3 candidate profile added. New v2 schema migration and native NVIDIA protocol qualification are not implemented |
| 03 Qwen conversation/tools | NOT IMPLEMENTED | Existing advisory guidance remains. Streaming, durable conversation, validated/idempotent tools, cancel/reconnect and endpoint capability probing still required |
| 04 optional Phonon | NOT IMPLEMENTED | No mandatory dependency/weights added; pinned engine/license, English fixture and actual 2-vCPU measurements still required |
| 05 A2A | NOT IMPLEMENTED | Official SDK client, durable jobs, reconciliation, cancellation and citations remain required |
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
| Final Python pytest with verified age | 124 passed, no skips, one existing Starlette warning | Local backend, real FFmpeg/age; mocked provider/GitHub transports |
| Existing config/Laya/security subset | 41 passed | Mock transport, not provider integration |
| Full Playwright with both integration flags | 38 passed in 1.2m | Native browser encoding and real local HTTP/media/index; synthetic camera/mic and inference fixtures |
| npm --prefix web run lint | 0 errors, one existing Architecture unused-variable warning | Static analysis |
| npm --prefix web run build | PASS | Production Next.js / TypeScript build |
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

Continue Gate 02's explicit versioned configuration migration before writing new
conversation/tracker/ASR/A2A YAML fields. Preserve original v1 history/export/rollback
and prove restart plus encrypted backup compatibility. Keep detector gateway and
native NVIDIA protocols distinct. Then implement Qwen streaming/tool execution
with a fake OpenAI server, followed by Phonon and official A2A SDK fixtures.

After code completeness, rerun CPU Docker, perform a private auth/provider/resource
qualification and a recovery drill. Deployment and production schedule activation
still need explicit approval. A draft PR does not authorize those actions.


## Reviewable implementation commits

- `1dea8750e5d3414786c27ab26927ef1598594c0e`: exact source audit and baseline.
- `39af3896046dceae48aa3e8fa76c8af7983f4840`: bounded streaming WebM ingestion fix/tests.
- `54d2c70bb974f0fb743c923193e886d20885f4ef`: browser recorder/framing/lifecycle and integration tests.
- The enclosing documentation commit adds qualification logs, disabled profile,
  architecture and changelog. Final delivered HEAD is recorded in the draft PR.
