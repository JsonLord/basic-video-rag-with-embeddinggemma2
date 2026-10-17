# Codex prompt — Visual Mentor v2: Video RAG UI restoration and feature integration

You are the lead engineer on `https://github.com/JsonLord/basic-video-rag-with-embeddinggemma2`.

**Governing new specification:** `spec.md` (Visual Mentor v2). Read it fully before touching code. The owner is changing course: **this project is an enhancement of the original Video RAG application and UI**, not an independent ultra-light mentoring dashboard. The currently deployed `Leon4gr45/openweb` UI does not meet expectations.

## Branch selection (mandatory)

1. Fetch remotes and inspect `main`, `feature/visual-mentor` (`245b686c916f0fcb0aff50b305e27f399c32910d` at the last review), and `deploy-huggingface-space-2826124284938220779` (PR #1). Verify latest commit SHAs before acting.
2. Create a **new development branch from `main`**, named `feature/video-rag-mentor-v2`. Do NOT branch from the deployment PR, and do NOT merge `feature/visual-mentor` wholesale.
3. Treat `main/web/` as the visual, functional and UI component **source of truth**. Port only the required **tested** backend modules, adapters, security, tests, camera lifecycle logic and compatible Docker work from `feature/visual-mentor`. Cherry-pick/file-port intentionally and document the porting decisions. Keep `main` and prior feature branches unchanged.
4. Replace the OLD `main`-branch `spec.md` on the new branch with the attached Visual Mentor v2 specification if it has not already been replaced.

## Product intent

Create a cohesive Video RAG + Visual Mentor web app: original Library/Search/Ask/Experiments/Architecture/clip-player UI preserved and improved; add high-quality Live dual-camera workspace, integrated mentor observations, rich Models & Routing tab with YAML upload and parallel Laya/NVIDIA routing, remote Whisper/VLM/embedding adapters, media import/indexing and CPU-affordable background processing.

**Stop optimizing for ~200 MiB memory.** HF CPU Basic is 2 vCPU / 16 GB RAM / 50 GB ephemeral storage. Optimize responsiveness and product functionality while measuring RAM, CPU, provider latency and costs. Retain remote inference; DGX must not be needed. Local FFmpeg and small CPU image/video helpers are permitted; no large on-Space inference models.

## Mandatory work sequence

**Step 0 — Audit & UI baseline (do first).** Inspect current repo and previous branch; write `docs/v2-ui-baseline.md` (which original components/pages/styles are protected), `docs/v2-porting-plan.md` (which feature-branch modules to port, reject or rewrite). Take desktop/mobile baseline screenshots using seeded, deterministic library data, not a blank DB. Inspect `openweb` only if accessible with approved credentials. Do not invent a screenshot comparison if inaccessible.

**Step 1 — Original Video RAG parity.** Make Library (`/`, default landing page), Search, Ask, Experiments, Architecture and video details work, and preserve design tokens, dense cards, metadata, clip modal, inline source playback and citations. Do not replace them with generic panels. Add screenshot/visual regression tests, e.g. Playwright, and seeded content. No further feature work until this UI gate passes.

**Step 2 — RAG, media and remote inference.** Port existing versioned-index/remote-LLM/provider/security code from `feature/visual-mentor`; preserve functional `/api` and `/media` routes. Re-enable useful video ingestion: browser upload, bounded background FFmpeg thumbnail/proxy/segment tasks, remote Whisper transcription, indexed text/captions, provider-compatible multimodal indexing, resumable/retryable job status. Preserve old MRL/RRF/experiments only where technically valid. Never claim text-only embeddings reproduce frame/video/audio/fused shared-space behavior.

**Step 3 — Live UI that looks native.** Build `/live` within the original UI system. Integrated laptop camera + external USB webcam through HTTPS `getUserMedia` in the browser; two independent simultaneous previews when available; controls, 1-2 fps sampled transfer default, overlay geometry, provenance, timeline, mentor guidance, push-to-talk, clear consent. Reuse lifecycle and stale-observation safety tests from old feature branch.

**Step 4 — Full Models & Routing Studio.** Improve `/models` to professional provider cards, route matrix/visual graph, per-session overrides, synthetic test, YAML file input + editor + validate/diff + atomic apply/rollback/export + profiles, trace latency/errors, authorized destinations. Support single, fallback, parallel, sequential and conditional execution; typed fusion of NVIDIA detection boxes and Laya semantic decisions without invented geometry. Laya's available API contract is established only for limited advisory/synthetic use; check live credentials/capabilities. Do not assume NVIDIA or Whisper models are live without tests.

**Step 5 — Mandatory 12-hour private GitHub backups (new release blocker).** Implement the backup contract in `spec.md` Section 9. Propose/create (only when authorized) a *separate private* backup repository, preferably `JsonLord/visual-mentor-backups`. Its GitHub Actions workflow must run at `17 0,12 * * *` UTC and support `workflow_dispatch`, avoid double runs, and report late/missing/failed backups. Use external durable storage as the authoritative source when available, not the HF ephemeral filesystem. Build consistent encrypted state snapshots (SQLite backup API), redacted YAML routing/profile history, transcripts, metadata, job state and versioned index manifests/artifacts. Large media must go to private object storage (or a specifically approved budgeted LFS route) and have SHA-256 inventory/verified availability in GitHub; never mistake GitHub-only metadata for a full-media backup. Encrypt snapshots *before* GitHub; require out-of-band recovery key storage. Add backup/restore scripts, admin-only backup status, retention rules, monitoring, docs and failure-mode tests. Test a manual GitHub Actions run and verify restoration into an isolated clean staging directory. Never claim backup enabled until the actual private workflow has run and a restore is demonstrated. Keep repo creation, credential provisioning and production activation approval-gated.

**Step 6 — Packaging and staging.** Produce Docker image for a private HF Space, exactly one public app port 7860, working same-origin `/api` and `/media`, responsive original Next.js UI. Audit PR #1 changes individually; eliminate competing `next.config.ts` vs `next.config.mjs`. Arrange external durable storage/backups because the 50 GB Space disk is ephemeral and permanent built-in storage cannot be presumed. Document private authentication and both app-level user/admin controls. Build locally, run UI/functional/security tests and measure 2-vCPU/16GB performance. Do not modify `Leon4gr45/openweb` until staging + explicit user approval.

**Step 7 — User-facing approval package.** Deliver a screenshot comparison of `main` vs new `/`, `/search`, `/ask`, `/live`, `/models`, a UI/functional parity checklist, functional tests including a realistic sample library, Docker measurements, live vs mocked provider test table, and precise staging deployment/rollback instructions, private backup repository/workflow evidence, backup coverage, most recent successful run and restore procedure. Identify constraints that still require physical cameras, credentials or private HF access. Commit all work on `feature/video-rag-mentor-v2` and push branch if permitted. Do not merge or deploy production without explicit approval.

## Non-negotiable acceptance criteria

- Landing page defaults to the **original-style Library**, not Live/Models/status.
- Existing Library/Search/Ask/Experiments/Architecture/video-detail functions pass with seeded data.
- Video results have real playable clip links and timestamped citations; media seek/Range works.
- New Live/Models look like parts of the original Video RAG site, not an unrelated administrative dashboard.
- Video upload -> transcription -> segmentation -> embeddings -> search/Ask actually works for a verified remote provider pipeline (or reports each unavailable dependency truthfully).
- User can choose laptop camera, USB camera or both; test synthetic devices automatically and real hardware manually.
- YAML upload and routing can run Laya, NVIDIA or both in parallel; failure isolation and sensitive egress authorization retained.
- Working private HF Docker packaging within 2 CPU / 16 GB RAM, with no DGX coupling, plus a **separate private GitHub backup repository** with 12-hour scheduled encrypted snapshots, asset coverage, failure alerts, and a verified clean restore.
- Regression evidence is real; do not claim a mocked provider or simulated camera is a live qualification.

## Engineering rules

Preserve existing design components and API contracts; use minimal refactors rather than framework replacement. Add test coverage and useful errors for missing providers. Every new route and feature must have actual UI interactions, not placeholders. Use typed interfaces, safe YAML parsing, SSRF protection, redacted secrets, bounded tasks, cancellable requests and strict provider capability checks. If a dependency is unavailable, continue implementation of independently testable parts while listing the blocker. Do not make unauthorized network changes or expose new ports. Maintain a changelog and meaningful commits per phase.

**Start now:** Show concise branch comparison and porting plan, create the new branch from `main`, capture the original UI baseline, then continue through implementation. Do not stop after producing only a plan unless genuinely blocked.
