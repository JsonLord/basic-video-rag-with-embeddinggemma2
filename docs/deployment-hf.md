# Private Hugging Face Docker Space

## Local development

Use the existing isolated checkout (no additional Git worktree). Python 3.12+, uv, Node 24 and FFmpeg are available in the prepared cloud environment. FFmpeg remains optional/offline; live requests never invoke it.

```bash
cd /workspace/basic-video-rag-with-embeddinggemma2
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PROJECT_ENVIRONMENT=/workspace/visual-mentor-venv
uv sync --frozen --group dev
cd web
npm ci --cache /workspace/.cache/npm --no-audit --no-fund
npm run build
cp -r .next/static .next/standalone/.next/
cd ..
export VM_STATE_DIR=/workspace/.visual-mentor/state
/workspace/visual-mentor-venv/bin/python scripts/cloud-start.py
```

The single frontend port is 7860; FastAPI binds loopback 8000 only. Local camera previews work without inference providers. Models/config changes require an administrator token and writable state; frame analysis also requires a separate user token and configured approved providers. Enter tokens in the relevant UI tab. Supply values securely; never commit them or enable automatic fallback to local models.

Validation:

```bash
/workspace/visual-mentor-venv/bin/python -m pytest -q
cd web
npm run lint
npm run build
# Run against a started app, using system Chromium in this environment:
CHROMIUM_PATH=/usr/bin/chromium npx playwright test
```

On another machine, set CHROMIUM_PATH to a supported Chromium installation or install Playwright's browser using `npx playwright install chromium` and adjust executablePath. The automated browser suite uses simulated devices and mocked providers; it cannot establish real USB behavior or live inference quality.

## Deploy (manual; not performed)

1. Create a Hugging Face Space with Docker SDK, CPU Basic, and **private** visibility. Choose persistent storage if required.
2. Push the reviewed feature branch files to the Space repository. The README already declares `sdk: docker` and `app_port: 7860`. A repository's GitHub visibility does not set Space visibility.
3. In **Space Secrets**, set distinct, random VM_ADMIN_TOKEN and VM_USER_TOKEN (at least 24 characters), plus only the provider API keys you actually use. In **Variables**, set VM_ALLOWED_HOSTS to exact comma-separated approved public inference hostnames, and provider endpoint variables from env.example. VM_ALLOWED_ORIGINS can explicitly contain the Space application origin. Never put credentials in YAML, frontend variables or build arguments.
4. For persistent config, set VM_STATE_DIR=/data/visual-mentor and ensure the mounted directory is writable by uid 1000. Put library/index data on protected persistent storage, set VRAG_DATA and VRAG_INDEX_DIR accordingly. Without VM_STATE_DIR, the shipped preview-only profile remains read-only. Without a persistent mount, configured history is ephemeral across rebuilds.
5. Open Models & Routing, enter the admin token, load current config, and select/upload a template. Replace placeholder model IDs with verified IDs, declare actual capabilities, validate/diff, then apply. Use synthetic provider tests before enabling sensitive routing. The Laya adapter is source/captured-contract tested and has passed a synthetic live request. NVIDIA, Whisper and other OpenAI-compatible providers still require actual endpoint verification. Choose only verified providers for enabled features.
6. Verify `/api/health`, library and media seeking; explicitly start cameras and authorize transfers only after approving destinations. A camera works only in an HTTPS browser/secure context. If embedding model/endpoint changes, use the separate versioned transcript re-indexing command in providers.md.

Build locally with `docker build -t visual-mentor .`, then `docker run --rm -p 7860:7860 --memory=1g --cpus=2 visual-mentor`. Supply secrets through your platform's supported secure environment injection rather than command-line values. The container runs as uid 1000 and supervises both processes; either process failure stops the other. Health uses the same single public-origin proxy path.

## Managed build proxy

The onboarding host requires proxy DNS mapping inside Docker builds. The release-review build command preserves the existing Docker configuration and credentials, uses a writable Buildx state directory, and maps the existing proxy hostname without host networking:

```bash
BUILDX_CONFIG=/workspace/.cache/buildx docker --host=unix:///var/run/docker.sock build \
  --add-host "proxy:$(python -c 'import socket; print(socket.gethostbyname("proxy"))')" \
  --build-arg HTTP_PROXY --build-arg HTTPS_PROXY \
  --secret id=build_ca,src="$SSL_CERT_FILE" -t visual-mentor:validation .
```

This maps the existing platform proxy and mounts its trusted CA during package installation only. It does not disable TLS, package signatures, checksums, or bake credentials/CA into the runtime image. Standard HF builders need no host-specific proxy flags. Docker COPY assigns application ownership explicitly because the onboarding host creates private files by default.

## Manual acceptance still required

Real laptop + USB cameras simultaneously, device contention/switching, permission revocation, mirrored/oriented captures, microphone support in the target browser, actual provider protocols/credentials, provider latency/quality, persistence across rebuilds, Space access control and memory under live inference traffic. The current report measures CPU startup and HTTP/synthetic workload only. No Hugging Face deployment or live provider success is claimed.


## Exact release procedure (approval required before push)

1. Review docs/release-readiness.md and resolve its mandatory gates. Select a **new private Visual Mentor Space**; the supplied needle-router Space is an inference service and must not be overwritten. No Space creation or push was performed during qualification.
2. Create the target in the HF UI: Docker SDK, CPU Basic, visibility Private. Record its repository ID as ACCOUNT/visual-mentor. Provision persistent storage if configuration/library state must survive rebuilds. Do not rely on README metadata for privacy.
3. In Space Secrets, provision distinct random VM_ADMIN_TOKEN and VM_USER_TOKEN (at least 24 characters). Add provider API keys only for actual selected endpoints: VLM_API_KEY, EMBEDDINGS_API_KEY, WHISPER_API_KEY, NVIDIA_DETECTION_API_KEY, and LAYA_API_KEY only if required by that gateway. Do not use NEXT_PUBLIC_ variables for secrets.
4. In Space Variables, set VM_ALLOWED_ORIGINS=https://ACCOUNT-visual-mentor.hf.space using the **actual** app hostname shown by HF, VM_ALLOWED_HOSTS to exact approved inference hostnames, and the corresponding *_BASE_URL variables. LAYA_BASE_URL is the root URL; OpenAI-compatible URLs normally include /v1. Do not set VRAG_API_URL to a DGX/external service; production proxies to bundled loopback FastAPI only.
5. To enable persistent configuration, create /data/visual-mentor owned by uid 1000 and set VM_STATE_DIR=/data/visual-mentor/config. Set VRAG_DATA=/data/visual-mentor/library and VRAG_INDEX_DIR=/data/visual-mentor/indexes/MODEL-VERSION when supplying a corpus/index. With no state directory, profiles are read-only; using an ephemeral directory does not guarantee persistence. Keep enabled-provider secrets out of the state directory.
6. After explicit deployment approval, configure HF Git authentication securely and run from this feature branch:

```bash
# Set SPACE_ID to the newly approved private application Space, not needle-router.
# No token belongs in this URL or command history.
git status --short
git rev-parse HEAD
git push "https://huggingface.co/spaces/${SPACE_ID}" HEAD:main
```

7. HF builds Dockerfile and exposes 7860. Require successful /api/health through the HTTPS app origin, uid 1000 and no local model packages/downloads. Anonymous access to the actual private app and media/API must be denied by HF; an authenticated HF session should see the UI. A user token must still get 401 on admin configuration paths; missing user auth must get 401 on sessions/inference. Enter the separate application tokens in the appropriate tabs.
8. Load current configuration. Choose laya-only, detector-only, laya-nvidia-hybrid, or the general hybrid template; replace every placeholder model ID and configure required endpoint variables. Validate/diff before apply. Run synthetic provider tests; actual NVIDIA/Whisper/VLM/embeddings are not preverified by this repository. Do not enable a detector/tracker unless it implements the documented contract. Laya supplies advisory noul scores, not generative guidance or boxes.
9. With explicit permission, manually verify laptop+USB previews and device IDs, contention/switching, portrait/mirror/resize overlays, per-camera opt-in, slow-inference backpressure, hide/navigation/revocation teardown, and microphone start/stop. HF's embedding iframe must delegate camera/microphone permissions; use the app's direct HTTPS origin if necessary. Confirm server/provider retention policy before transmitting personal frames.
10. Apply a config revision, restart the Space through its approved controls, and verify the same revision/profile and library remain. Confirm the target VM_STATE_DIR is actually on persistent storage. Use Models & Routing Restore Version for configuration rollback (a new revision is created). Application rollback requires a separately reviewed/approved Git revision and push.

Local offline qualification, without publishing any host port:

```bash
/workspace/visual-mentor-venv/bin/python scripts/qualify-release.py --image visual-mentor:release-review
```

This creates a temporary, network-disabled CPU container, tests bearer/origin checks and configuration apply/rollback, recreates it with its own temporary Docker volume, verifies persistence, and deletes only those test resources. It does not prove private HF gateway behavior or authorize deployment. For resource measurements of the selected image, set VM_RUNTIME_IMAGE=visual-mentor:release-review when running scripts/measure-runtime.py.
