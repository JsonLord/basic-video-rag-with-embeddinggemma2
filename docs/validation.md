# Visual Mentor v2 validation

The current qualification is [v2-release-readiness.md](v2-release-readiness.md),
with raw evidence under [v2-evidence](v2-evidence/) and the
[UI comparison](v2-evidence/ui-comparison.html).

The original main UI was captured before new feature work. Local sample/CPU and
mock-provider tests are explicitly distinguished from live Laya and from pending
HF, physical camera, NVIDIA, Whisper, VLM, embedding and private-backup gates.

Reproduce backend and browser tests with an isolated data directory. For the extra
real frontend/backend sample smoke test, start FastAPI on loopback 8000:

```
VRAG_DATA=/tmp/mentor-test-data VM_STATE_DIR=/tmp/mentor-test-config \
  python -m uvicorn vrag.api:app --host 127.0.0.1 --port 8000
```

Then, in a separate shell:

```
python -m pytest -q
npm --prefix web run lint
npm --prefix web run build
cd web && VM_FULLSTACK=1 CHROMIUM_PATH=/usr/bin/chromium npx playwright test
```

Playwright starts its own loopback web server on the existing app port 7860. Real
age encryption tests require `age`/`age-keygen` on PATH (or AGE_BIN selecting age);
otherwise those tests are skipped rather than reported as encryption evidence.
The recorded run installed age in a temporary tool directory and had no skips.

Neither test suite starts DGX/model services or sends production/camera data.
`check-laya.py --synthetic` is a separate, explicit live-generated-image test.
Docker qualification starts only its own ephemeral network-isolated containers,
publishes no ports, and cleans up its own volumes/containers. Private Space and
backup workflow activation require the runbooks' explicit approvals.

## GitHub-native backup refactor

The subsequent backup qualification and unresolved live gates are recorded in
[github-backup-migration.md](github-backup-migration.md). Successful recovery unit
and subprocess tests use real age/SQLite/FFmpeg with mocked GitHub transport; they
are not a successful live GitHub or private-HF scheduling integration test.
Opt-in live drill: `AGE_BIN=/path/to/age python tests/live_github_recovery.py`.
It writes only a unique test namespace and refuses to claim success unless a fresh
application recovers all file hashes after destruction of its source/stage.
