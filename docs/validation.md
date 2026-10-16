# Validation report — 2026-10-16

Historical evidence for commit 4549ff5. See [release-readiness.md](release-readiness.md) for the subsequent qualification, fixes and updated Laya integration results.

Branch: `feature/visual-mentor`. Baseline: `7f8922cad8adb7e73a5f95ecfbf5b1a73e5bd46f`. Application source through `10a591d`; subsequent report commit records final measurements. No production deployment or DGX services were changed.

## Final executed checks

| Check | Actual result |
| --- | --- |
| Python backend tests | 35 passed; no skipped/disabled tests; one Starlette TestClient/httpx deprecation warning |
| Playwright / system Chromium 154 | 2 passed (6.7 seconds); simulated devices and mocked backend inference responses |
| `npm run lint` | passed, no lint errors |
| `npm run build` | passed, TypeScript and production prerender/standalone output |
| `uv sync --frozen --group dev` | passed and repeatable; CPU dependencies only |
| Docker build | passed, signatures/TLS/hash checks retained; non-root runtime |
| Container functional requests | 180 successful requests across Live, Models, Library, Search, Ask, library/stats/health/OpenAPI through one port |
| Forbidden package inspection | torch, transformers, sentence_transformers, vllm all absent |
| Saved startup restart | restarted supervisor, health reported remote-only, library returned valid empty list |
| `git diff --check` | passed |

Backend tests cover safe YAML and secret-value rejection, capabilities, config revision conflict/apply/rollback/restart, session ownership/consent, stale frames, origin and payload checks, normalized boxes, provider wire contracts, fallback/parallel/sequential/conditional routing, cancellation, timeout/concurrency/circuit behavior, no text-derived boxes, incompatible embedding endpoint rejection, library/search/Ask with citations, precomputed frame fallback and HTTP Range playback. Browser tests verify dual simulated previews, opt-in transfer, independent stop, analyzed-frame overlay geometry, teardown and profile apply. They do not verify real USB hardware, actual inference or semantic model quality.

## CPU measurements

Image: `sha256:b184a2493d5b2e40ce3f06225b985ccd476f302577cc436ee72e399908ad787e`.

Measured with `python scripts/measure-runtime.py` under 2 CPU / 1 GiB limits, no GPU and no configured providers. Full numbers are retained in [runtime-metrics.json](runtime-metrics.json).

| Metric | Actual |
| --- | --- |
| Uncompressed image | 441,968,902 bytes (421.5 MiB) |
| Launch to successful proxied health | 8.035 seconds |
| Idle aggregate app RSS | 179.4 MiB |
| Sampled peak app RSS | 203.3 MiB |
| Container cgroup memory peak | 139.3 MiB |

RSS sums the supervisor and descendant application processes, excluding measurement processes; shared pages can be counted more than once. Peak RSS samples every 25 ms plus idle/post-workload snapshots. Cgroup accounting differs and should not be equated with aggregate process RSS. Measurements cover CPU startup and HTTP traffic; live provider latency and peak memory with real camera/audio requests remain unmeasured. These observations meet the idle/peak memory targets for this workload only.

## Milestones and remaining gates

| Milestone | Outcome |
| --- | --- |
| M0 baseline | audited/documented; original CPU startup failure reproduced |
| M1 cloud RAG | implemented and regression/contract tested; real embedding/index and VLM integration unverified |
| M2 Docker | CPU image built and functionally run; HF deployment unrun |
| M3 dual camera | implemented and simulated-browser tested; laptop + USB acceptance manual |
| M4 routing studio | implemented registry/matrix, YAML profiles, validation/diff/apply/export/rollback/test/dry-run; mocked browser and real backend API tests |
| M5 perception/STT | remote VLM/embeddings/Whisper and detection gateway contract-tested; actual NVIDIA endpoint unverified; Laya inference blocked pending reachable schema |
| M6 mentoring foundation | advisory task state, observation/speech-to-guidance boundary, future remote research protocol; no autonomous agent |

The user supplied `https://leon4gr45-needle-router.hf.space` and the health/ready/info/System-1 endpoint names. The platform proxy returned HTTP 403 at CONNECT before contacting the service. Endpoint names alone do not establish request fields or image/decision response semantics. Laya therefore remains explicitly unavailable with a disabled template, without invented capabilities or guessed payloads. Review/save the environment draft, supply LAYA_API_KEY securely, publish, then retry metadata/OpenAPI discovery. No pasted credential value was copied to code/configuration.

The saved environment draft contains tested install_script and start_skill, exact Laya hostname access, LAYA_BASE_URL, VM_ALLOWED_HOSTS, VM_STATE_DIR and the LAYA_API_KEY requirement. Draft persistence is confirmed; it is not proof of runtime application or publication. No fresh-task restoration, live provider success, real USB camera result, provider-side retention policy, or private HF deployment is claimed. NVIDIA services require a verified explicit gateway as documented in providers.md. Full mentoring autonomy is outside v1.

Security limits and prerequisites (single-user bearer auth, admin-controlled trusted DNS/egress, HTTPS and persistent storage) are in [security.md](security.md). Deployment and secret provisioning steps are in [deployment-hf.md](deployment-hf.md).

Setup failures from eager CUDA imports, build-time Google Fonts, container proxy DNS/CA, non-root file permissions, stale local server processes and disk pressure were diagnosed and corrected. Obsolete task build caches/images were removed; the final image and source remain. No failed checks remain unexplained.

## Implementation commits

```
f3d804f docs: record Visual Mentor baseline and milestone plan
a55e3d4 feat: add CPU-only runtime and remote RAG provider foundation
8ca4937 feat: package one-port CPU deployment and authenticated live API
ee42d6d feat: add explicit dual-camera capture and correlated observations
543adb7 feat: add routing YAML studio and atomic configuration lifecycle
3547eef feat: harden remote routing and RAG with deterministic contract coverage
e79d5ad feat: add advisory mentoring state and document deployment boundaries
10a591d fix: bound DNS checks and report unmet routing quorum
```

## Changed files

```
.dockerignore
.gitignore
Dockerfile
README.md
config/__init__.py
config/examples/detector-only.yaml
config/examples/disabled.yaml
config/examples/hybrid.yaml
config/examples/laya-pending.yaml
config/examples/vlm-only.yaml
config/schema.py
docs/api.md
docs/architecture.md
docs/deployment-hf.md
docs/providers.md
docs/runtime-metrics.json
docs/security.md
docs/validation.md
env.example
pyproject.toml
requirements-runtime.in
requirements-runtime.txt
scripts/cloud-start.py
scripts/measure-runtime.py
scripts/reindex-remote.py
tests/test_api_config.py
tests/test_config.py
tests/test_live.py
tests/test_providers.py
tests/test_rag.py
tests/test_routing.py
tests/test_runtime.py
uv.lock
vrag/api.py
vrag/config.py
vrag/index.py
vrag/mentor_api.py
vrag/providers.py
vrag/remote.py
vrag/research.py
vrag/routing.py
vrag/settings.py
web/next.config.ts
web/package-lock.json
web/package.json
web/playwright.config.ts
web/src/app/ask/AskView.tsx
web/src/app/globals.css
web/src/app/layout.tsx
web/src/app/library/page.tsx
web/src/app/live/page.tsx
web/src/app/models/page.tsx
web/src/app/page.tsx
web/src/app/search/SearchView.tsx
web/src/components/AccessToken.tsx
web/src/components/Controls.tsx
web/src/components/Nav.tsx
web/src/components/NavLinks.tsx
web/src/lib/api.ts
web/src/lib/mentor.ts
web/tests/live.spec.ts
```
