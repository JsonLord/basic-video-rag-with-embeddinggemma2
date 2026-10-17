---
title: Video RAG · Visual Mentor
sdk: docker
app_port: 7860
---

# Video RAG · Visual Mentor v2

The original Library, Search, Ask, Experiments, Architecture and clip-player UI,
with remote inference, a dual-camera Live workspace and Models & Routing studio.
The landing page is Library. Without a connected private-library token it shows
an immutable synthetic sample corpus, keyword retrieval and labeled evidence
extracts. No model inference or benchmark quality is implied by samples.

Run a CPU-only development environment (Python 3.12+, Node 24+, FFmpeg):

```
python -m venv .venv
.venv/bin/pip install -r requirements-runtime.txt
npm --prefix web ci
PYTHON=.venv/bin/python bash scripts/dev.sh
```

Open port 7860. FastAPI stays on loopback 8000. Configure independent
VM_USER_TOKEN/VM_ADMIN_TOKEN (at least 24 random characters), VM_ALLOWED_ORIGINS,
VRAG_DATA and VM_STATE_DIR in environment settings; never commit values.
No local inference services are started. For a production container:

```
docker build -t video-rag-mentor:v2 .
```

See [HF staging/deployment steps](docs/deployment-hf.md),
[v2 qualification and remaining gates](docs/v2-release-readiness.md),
[private backup/restore](docs/backup-restore.md), and
[porting decisions](docs/v2-porting-plan.md). Private Space deployment, backup
repository creation, credentials and activation remain approval-gated.
The base Space disk is ephemeral; local files alone do not establish durability.

Browser uploads are capped at 64 MiB/30 minutes, with one processing worker and
two simultaneous uploads. Jobs prepare CPU H.264 proxies, keyframes and timestamped
segments, transcribe via remote Whisper-compatible API and build isolated remote
text indexes. Missing providers become explicit blocked jobs with retry/manual
transcript support. Models/routing use strict schema version 1, not the illustrative
version-2 YAML in the product specification. All example routes start disabled.

Large multimodal inference stays remote. Text adapters cannot encode images,
video or audio into a shared vector space. Historical MRL/RRF indexes and charts
remain viewable where compatible; [original research documentation](docs/original-research.md)
is retained separately and is not this cloud runtime's setup procedure.

Validation:

```
python -m pytest -q
npm --prefix web run lint
npm --prefix web run build
cd web && CHROMIUM_PATH=/usr/bin/chromium npx playwright test
```

Install `age` to run actual encrypted backup tests. Test tooling requires pytest,
pytest-asyncio and Playwright; Python dev dependencies are in the uv dev group.
