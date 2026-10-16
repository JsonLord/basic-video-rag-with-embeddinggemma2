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
5. Open Models & Routing, enter the admin token, load current config, and select/upload a template. Replace placeholder model IDs with verified IDs, declare actual capabilities, validate/diff, then apply. Use synthetic provider tests before enabling sensitive routing. Laya/Jev remains disabled until its actual protocol is supplied and implemented.
6. Verify `/api/health`, library and media seeking; explicitly start cameras and authorize transfers only after approving destinations. A camera works only in an HTTPS browser/secure context. If embedding model/endpoint changes, use the separate versioned transcript re-indexing command in providers.md.

Build locally with `docker build -t visual-mentor .`, then `docker run --rm -p 7860:7860 --memory=1g --cpus=2 visual-mentor`. Supply secrets through your platform's supported secure environment injection rather than command-line values. The container runs as uid 1000 and supervises both processes; either process failure stops the other. Health uses the same single public-origin proxy path.

## Managed build proxy

The onboarding host requires proxy DNS mapping inside Docker builds. The verified local build command is:

```bash
DOCKER_CONFIG=/workspace/.docker docker build --network host \
  --add-host "proxy:$(python -c 'import socket; print(socket.gethostbyname("proxy"))')" \
  --build-arg HTTP_PROXY --build-arg HTTPS_PROXY \
  --secret id=build_ca,src="$SSL_CERT_FILE" -t visual-mentor:validation .
```

This maps the existing platform proxy and mounts its trusted CA during package installation only. It does not disable TLS, package signatures, checksums, or bake credentials/CA into the runtime image. Standard HF builders need no host-specific proxy flags. Docker COPY assigns application ownership explicitly because the onboarding host creates private files by default.

## Manual acceptance still required

Real laptop + USB cameras simultaneously, device contention/switching, permission revocation, mirrored/oriented captures, microphone support in the target browser, actual provider protocols/credentials, provider latency/quality, persistence across rebuilds, Space access control and memory under live inference traffic. The current report measures CPU startup and HTTP/synthetic workload only. No Hugging Face deployment or live provider success is claimed.
