# Gate 02 completion and Gate 03 foundation — 23 October 2026

**GO for continued Gate 03 implementation with synthetic providers. NO-GO for full
v3 release/deployment.** Starting HEAD is
`7c2c1a87164d94a49105f374580703ff61e7bf1c`, on the existing
`feature/visual-mentor-v3-live` branch and draft PR #3. Gate 02 core commit is
`3ac1c24`; final delivered HEAD is recorded in the PR and final delivery message.
No production Space, DGX, Docker service, credentials, backup checkpoint, workflow
schedule or environment allowlist was activated/changed in this task.

## Migration and revision strategy

V1 Provider/Configuration fields and capability validation stay unchanged. The
new `config/v2.py` contains distinct ProviderV2/ConfigurationV2 types. parse_yaml
uses explicit schema-version dispatch and still rejects anchors, duplicate keys,
unknown fields, unsupported adapters/capabilities and unknown versions. An explicit
`migrate(v1)` returns a new v2 object; it never changes its input or saved history.

The administrator's `/api/config/migrate` previews YAML only. Studio buttons expose
migration and optional HF-default insertion; validation and CAS apply remain
separate. Old serialized JSON objects retain their original keys/values (including
omitted default fields) when a new revision is appended; JSON formatting is not
promised byte-for-byte. History export is protected at `/api/config/history/{revision}`.
Rollback appends the original typed schema version rather than silently upgrading
it. Restart loads mixed v1/v2 histories. Snapshot copies remain isolated.

| Value | Meaning |
| --- | --- |
| version / schema_version | Typed configuration schema, 1 or 2 |
| history_revision | Monotonically appended configuration history position |
| config_version / expected_version | Legacy compatibility names for history revision, never schema version |
| routing_revision | Ephemeral, owned live-session override revision |
| capability_version | Provider adapter contract version; currently 1, separate from actual model qualification |

Backup formats and destinations are unchanged. The format-1 compatibility validator
and active GitHub format-2 coverage validator now dispatch by configuration version.
Real age encryption + mock GitHub transport tests destroy staging/source state,
restore mixed histories, reopen ConfigStore and compare the old objects. No live
GitHub upload, production recovery or scheduled activation was attempted.

## Runtime defaults and security

`vrag/runtime_config.py` overlays defaults into the existing provider registry; it
is not another settings/endpoint registry. The exact production HF variable/secret
names and precedence are documented in [hf-runtime-variables.md](hf-runtime-variables.md).

Explicit YAML roles win, including disabled roles. Otherwise configured HF values
supply disabled, public_only hf-conversation/hf-research entries. These references
use OPENAI_COMPATIBLE_URL, OPENAI_COMPATIBLE_MODEL, OPENAI_COMPATIBLE_API_KEY,
A2A_URL and A2A_TOKEN exactly. model_env resolves the selected model at dispatch;
explicit YAML model with no model_env overrides it. Live-session overrides reuse
existing identities only, cannot inject destinations and do not persist defaults.
Conversation-specific session selection/orchestration remains Gate 03 work.

The studio displays sanitized host/model information and boolean credential
presence, never secret/endpoint values in exported YAML. Invalid/unapproved
configured default URLs return an explicit configuration error; an authorized YAML
selection can override an invalid unused default. Missing optional integrations do
not stop local cameras or the original library. Every request retains HTTPS,
exact-host allowlist, public-address/DNS checks, proxy/TLS policy, no redirects,
per-provider concurrency and trust checks. Presence is not successful authentication
or health: live status remains not_checked. Conversation root and already-/v1 URLs
produce a single /v1/chat/completions path.

## Routing and geometry qualifications

All ten requested roles are discoverable in the studio. Four v2 presets are shipped:
Laya Fast, NVIDIA Precision, Hybrid and Custom. Every route in distributed examples
is disabled. The detection model remains an explicit replace-with placeholder; it
cannot be enabled before substitution. The A2A adapter and automatic remote framing
selection remain reserved/fail-closed; their roles cannot be enabled prematurely.
Audio transcription and browser framing/association retain their existing paths.

Synthetic transports verify Laya-only noul decisions, custom-gateway-only spatial
results, truly concurrent Hybrid requests and Custom fallback. Timeout/partial
failure statuses stay separate from successful outputs. Trust is checked on every
actual dispatch, including fallback. Cancellation closes parallel operations.
A2A dispatch fails before a network request. There is no new native NVIDIA adapter.

Fusion now applies conservative same-label IoU >=0.9 suppression rather than blindly
concatenating duplicate boxes. It retains contributing source, detection ID, box,
confidence and optional upstream object ID as evidence. Distinct IDs from the same
tracker are not suppressed. This is a display heuristic, not proof of physical
identity or calibrated cross-provider confidence. The representative source can
change when the highest-confidence provider changes; browser IDs remain scoped to
the actual source/camera. No cross-camera or cross-frame box fusion occurs.

Original frame/camera/capture timestamp/history revision flow through routing
statuses and observations. Schema and routing revisions are explicit. The server
rejects an observation when either history or session routing changes in flight;
the browser checks capture timestamp and routing revision as well as its existing
frame/request/dimension/geometry correlation. Stable browser association and all
Gate 01 record/replay/import/privacy regressions continue passing.

NVIDIA evidence is **mock custom detection-http contract evidence only**. No actual
native NVIDIA model/protocol is qualified. Laya remains narrow inspectability noul
scoring; no fabricated geometry, captioning, temporal tracking or latency SLA is
claimed. Historical live Laya evidence is preserved, not repeated with user media.

## Actual test evidence

Gate 02 was validated before beginning Gate 03:

- 144 backend tests passed, no skips, with checksum-verified age v1.3.2 and real
  FFmpeg/SQLite/local encryption; all provider/GitHub transports were mocked.
- 42 Playwright tests passed with simulated cameras/microphone, including the real
  local recording import/index/playback flow and new studio/provider switching.
- Production Next.js build passed. Lint: zero errors, one pre-existing Architecture
  unused-variable warning.
- Only the deliberately changed Models screenshots were updated. Live and original
  Video RAG page snapshots were preserved.

Gate 03 foundation subsequently brought backend coverage to 159 passing tests,
including real encrypted recovery of the tool idempotency ledger. Final browser,
build and lint logs are in `docs/v3-evidence/gate03/`; Gate 02's own checkpoint logs
remain in `docs/v3-evidence/gate02/`. No physical-device, live inference, new CPU/RSS,
p50/p95, cost, private HF or production recovery benchmark was performed.

Commands, using disposable state and the existing local fixture server:

```bash
AGE_BIN=/tmp/v3-age-v1.3.2/age/age VM_BACKUP_ENABLED=false \
  VRAG_DATA=/tmp/v3-g3-all/data VM_STATE_DIR=/tmp/v3-g3-all/state \
  /workspace/visual-mentor-venv/bin/python -m pytest -q
npm --prefix web run lint
npm --prefix web run build
# From web/, with the isolated v3_fixture_server on loopback 8000:
VM_FULLSTACK=1 VM_RECORDING_FULLSTACK=1 CHROMIUM_PATH=/usr/bin/chromium \
  npx --no-install playwright test
```

See v3-qualification.md for fixture startup instructions. Those HTTP/media/index
paths are real local execution; transcription/embeddings are deterministic fixtures.

## Gate 03 work begun, not complete

The existing Adapter now exposes a bounded OpenAI SSE text/tool-call stream. It
resolves the production environment model/key, uses the same destination controls,
semaphores and transport, and fails closed on auth errors/redirects/truncation.
Text is progressive; tool calls are assembled, bounded, fully validated and emitted
only after complete stream termination. A stream never executes a tool itself.

The typed registry covers dispatch_research, get_research_status, cancel_research,
retrieve_video_evidence and summarize_scene. Only explicitly registered handlers
are advertised. The default owned-session factory registers no research action.
Execution requires an ownership authorizer, validates arguments, rechecks permitted
refs/agent/consent, bounds concurrency and records idempotency in a new table in
existing jobs.sqlite. Replayed calls return the durable result; changed arguments
conflict. Interrupted operations stay outcome_unknown after restart instead of
blindly executing twice. Ledger capacity is bounded at 10,000 calls; integration
must provide lifecycle cleanup before general chat activation. Tool results are
bounded and exception text is never persisted. The encrypted recovery test proves
the ledger survives through existing backup scope without a new database path.

This is a tested foundation, not complete Gate 03: authenticated conversation HTTP/
SSE orchestration, durable conversation turns, frontend chat, context compaction,
turn/recursion budgets, user cancel/export/delete, grounded retrieval/scene handlers
and capability probing still require implementation. The registry's real ownership
callback is session_for; synthetic tests supply controlled authenticated callbacks.
There is no newly exposed inference endpoint and no real A2A handler/SDK dispatch.
Do not infer live Qwen or research success from fixture callbacks.

## Changed modules and next steps

- Schema/history: config/schema.py, config/v2.py, vrag/settings.py.
- Environment/providers/routing/API: vrag/runtime_config.py, vrag/providers.py,
  vrag/routing.py, vrag/mentor_api.py.
- Backup validator compatibility only: vrag/backup/__init__.py, vrag/backup/github.py.
- Browser: Live page, Models page, lib/mentor.ts; new gate02 test, stale-result
  tests and the two Models snapshots.
- Presets: config/examples/v3-{laya-fast,nvidia-precision,hybrid,custom}.yaml.
- Gate 03: vrag/conversation_stream.py, vrag/conversation_tools.py and foundation tests.
- Reports/tests: test_v3_configuration.py, test_v3_routing.py, HF runtime documentation,
  architecture/qualification/changelog and separate evidence directories.

CPU Docker remains **BLOCKED**: the last executed build (Gate 01) was denied at the
pinned Node manifest request to registry-1.docker.io. This task did not retry it,
change policy, use mirrors or restart services. An infrastructure operator must
approve the documented registry/auth/Debian/observed redirect destinations and a
real CPU build/startup must succeed before that gate changes status.

Continue full Gate 03 orchestration and UI from the tested boundary, then optional
Phonon and official A2A SDK/durable research jobs. Keep the draft PR open. Production
and recurring workflows remain inactive pending explicit authorization and live
private-HF/provider/device/resource/backup qualification.

## Implementation commit checkpoints

- Gate 02 core: `3ac1c248c69fb25f7b2bf660ddd968cd317d2bbb`.
- Gate 03 foundation and final provider probe/tracking checks:
  `7eb2de06abb0dc9c19d6abca4545763f55c91da1`.
- Readability-only TypeScript formatting: `7ed67b8b34a9cadafce0ca44361adc38f166eaee`.
- The enclosing report/evidence commit is the final delivered HEAD recorded in PR #3.

Final backend total is 159: Gate 02's 144 checkpoint, 13 Gate 03 foundation cases,
and two follow-up checks for text-only synthetic probes and required tracker IDs.
Final browser total is 42; final Next production build and lint pass as recorded.
