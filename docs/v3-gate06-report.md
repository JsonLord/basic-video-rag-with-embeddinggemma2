# Gate 06 integration qualification — 24 October 2026

**Production recommendation: NO-GO.** Diagnostics and local regression acceptance
are complete; missing live credentials/endpoints and the Docker CDN failure prevent
live-integration qualification. No blocked external test is described as passing.

Implementation SHA: `317fe5ce613f6d175653ffb0354870d9e319a989`.

Starting SHA: `75085f80e657ac5150951ab94d21192833049b8e`, existing branch
`feature/visual-mentor-v3-live`, existing Draft PR #3. Implementation/report commit
SHAs and final pushed head are recorded in the PR and delivery; the enclosing report
commit cannot name its own SHA. Gates 01/02/03/05 and historical evidence are preserved.

## Release-readiness matrix

| Gate / integration | Actual result | Remaining prerequisite |
| --- | --- | --- |
| Existing recording/framing/routing/conversation/research | PASS, fixtures + real local execution | Physical/private/live checks below |
| Qwen standalone qualifier | PASS, ten fixture cases | Real approved URL/model/key |
| Qwen live | BLOCKED_CREDENTIALS; zero HTTP requests | OPENAI_COMPATIBLE_URL/MODEL/API_KEY and application-approved host |
| A2A discovery | BLOCKED_CREDENTIALS; zero HTTP requests | Token visible in actual process, application hostname authorization, proxy path substitution |
| Live A2A research | NOT_AUTHORIZED_NOT_SUBMITTED | Discovery first, then separate explicit approval |
| NVIDIA native | BLOCKED_ENDPOINT_AND_CONTRACT | Actual authorized model/endpoint/numeric response and latency benchmark |
| Private HF production configuration | PREPARED_ONLY | Operator settings, private staging/deployment approval, real auth test |
| Docker daemon | PASS, existing managed 28.4.0 | No daemon/service restart performed |
| CPU Docker image | BLOCKED_REGISTRY_CDN | Pinned Node metadata/blob fetch Forbidden at production.cloudfront.docker.com |
| Container startup / RAM / CPU / mixed-load p50/p95 | NOT_RUN_BUILD_BLOCKED | Actual successful image and authorized workload |
| Optional Phonon-2 | SOURCE_REVIEW_ONLY, disabled | Separate isolated CPU/ASR/resource proof |
| Production deployment / backup schedule activation | NOT_PERFORMED | Separate explicit approval and remaining gates |

## Changes made

`scripts/qualify-qwen.py` and `vrag/qwen_qualification.py` implement bounded,
non-mutating model/basic/stream/tool/correlation/cancel/deadline diagnostics through
the existing validation and egress layers. They use secure environment values only,
write sanitized machine-readable evidence without overwriting an old file, and
record client TTFT/total latency only when a stream actually runs. No actual tools,
local inference, application state, remote research or model deployment is invoked.
Ollama/vLLM differences and endpoint-specific identity limits are documented in
[live-provider-qualification.md](live-provider-qualification.md).

A small registry fix makes the default DB import conditional on needing that DB.
The diagnostic can therefore reuse existing typed tool definitions without importing
jobs/mentor_api, opening state, or introducing another tool/provider registry. A
fresh-process fixture with an invalid-as-directory VM_STATE_DIR verifies this.
Production registered handlers, authorization, idempotency and backup architecture
retain their existing behavior.

New tests exercise the diagnostic's positive protocol flow and negative auth,
redirect, model mismatch, missing tools, timeout, credential, destination, output
preservation and standalone boundaries. A2A discovery tests reject over-limit plain
and compressed bodies before SDK parsing. HF configuration tests verify disabled
routes, explicit YAML precedence, public_only defaults, no identity activation and
server-only secret references. A browser test covers automatic highest-confidence
selection once, changed detection order/confidence, per-camera track IDs and loss.

The actual Next production build was run with five synthetic server-only credential
canaries in its child environment. `scripts/scan-frontend-secrets.py` scanned its
compiled browser assets and found no canary. The scanner prints variable names and
asset paths only, never secret values; missing assets/configuration cannot pass.
No production credentials were set/changed by this test.

## Live provider findings

The actual process has none of the three OPENAI_COMPATIBLE variables. The real Qwen
run exits BLOCKED_CREDENTIALS before creating a transport. `qwen-fixture.json` is a
separate, explicitly mocked seven-request run; its timings are not live latency.
Authentication enforcement and remote compute cancellation are never inferred
from a successful valid-key request or closing the client stream.

A2A_URL is present but A2A_TOKEN is absent and the selected agent hostname is not
in application VM_ALLOWED_HOSTS. The existing read-only probe stops without HTTP.
Actual deployed protocol, Agent Card identity/skills/URL, supported lifecycle and
proxy path-token substitution remain unverified. No live research task was submitted,
and this task does not request blanket authorization for one. The separate bounded
proposal is in live-provider-qualification.md for later review.

Primary NVIDIA source identifies NV-Grounding-DINO's native asset/poll/archive
contract, not a compatible `/detect` server on the user's infrastructure. No native
adapter or fabricated schema was added. Geometry/fusion/Hybrid/timeout/framing tests
are mock gateway and browser evidence only. Laya remains optional, with no new live
latency claim. See [v3-nvidia-adapter-decision.md](v3-nvidia-adapter-decision.md).

## Actual Docker diagnosis

A real build of the pinned current Dockerfile was attempted through the existing
managed daemon with the combined CA mounted as build_ca. Python metadata resolved;
Node resolution advanced to a registry CDN request, which failed Forbidden at
production.cloudfront.docker.com. The earlier registry manifest-only failure is
therefore not simply repeated as the new diagnosis. Signed URL query strings were
redacted from stored build output.

Environment metadata reported desired unrestricted networking with unknown actual
enforcement, while the executor policy snapshot still listed a restricted host set
without that CDN. An unsigned registry root probe returned 404; an unsigned CDN root
probe failed at the network layer. These observations do not conclusively attribute
the CDN error to proxy policy versus an upstream signed-CDN response. Operator
policy/proxy synchronization and exact-host diagnosis are required. No policy was
edited/published, mirror selected, TLS disabled, proxy bypassed or daemon restarted.

No Gate 06 image exists, so container startup and loaded/idle/peak RAM, CPU, camera
mixed workloads, ingestion/chat/A2A coexistence and p50/p95 are **unmeasured** (JSON
nulls). Python import checks are not substituted. The real local browser mixed
flow passed, but it is not a container resource benchmark or native inference test.

## Phonon and production preparation

Code/weights licensing, CPU packaging, English 16 kHz format, model bytes and ISA
requirements were inspected at pinned source/model revisions. Phonon-2 weights are
CC-BY-4.0 and code Apache-2.0. Package metadata includes Torch/Transformers; the
upstream declared 163,515,201-byte archive is not a resident-memory measurement.
Weights were not downloaded or loaded, and no POC changed the default runtime.
See [v3-phonon-feasibility.md](v3-phonon-feasibility.md).

[hf-production-checklist.md](hf-production-checklist.md) inventories exact operator
Variables/Secrets, YAML/trust precedence, application/private-HF authentication,
server-only credentials, encrypted GitHub recovery, resource work and approvals.
No Space or existing inference infrastructure was changed. Production workflows
remain inactive; optional local ASR is still separate/off.

## Test evidence

- **191 backend tests passed**, zero failures/skips, one existing Starlette warning.
  This includes real local FFmpeg, SQLite, age encryption/destructive restore and
  fresh-process A2A reconciliation with mocked external transports.
- **44 Playwright tests passed**, including all original page snapshots, native
  simulated-camera recording/import, actual local index/clip playback, reviewed
  speech, streaming/tool/research/reconnect flow and the new automatic framing case.
  No screenshot baselines were changed in Gate 06.
- **Next production build passed**. Lint: zero errors, one pre-existing Architecture
  unused-variable warning.
- **Compiled secret scan passed:** 26 browser asset files, 1,361,945 bytes, zero
  matches for the five synthetic server credential canaries. This is scoped evidence,
  not proof about every future custom secret name or the unbuilt Docker image.
- The age v1.3.2 test binary was downloaded from its official release and its SHA-256
  verified against release metadata; no verification bypass or new runtime dependency.
- Actual live Qwen and A2A probes: BLOCKED_CREDENTIALS. Native NVIDIA/private HF/live
  research: unrun for the stated reasons. Actual Docker build: failed as recorded.

Machine-readable summary and raw logs: `v3-evidence/gate06/`. The regression test
process sets A2A_URL empty to isolate fixture defaults from the real unfinished
configuration; the real provider probes use the inherited environment unchanged.
Browser fixtures explicitly opt into disposable /tmp state and mock upstreams.
All physical-device, inference performance, external auth, provider cost and actual
production recovery claims remain pending. Stop only this task's test server after
validation; do not restart or alter shared services.
