FROM node:24-bookworm-slim AS web
WORKDIR /build/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY web/package*.json ./
RUN --mount=type=secret,id=build_ca if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
RUN export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY"; apt-get update && apt-get install -y --no-install-recommends ca-certificates libatomic1 && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY requirements-runtime.txt ./
RUN --mount=type=secret,id=build_ca if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; pip install --no-cache-dir -r requirements-runtime.txt
COPY --chown=1000:1000 vrag ./vrag
COPY --chown=1000:1000 config ./config
COPY --chown=1000:1000 scripts/cloud-start.py ./scripts/cloud-start.py
COPY --from=web --chown=1000:1000 /build/web/.next/standalone ./web/.next/standalone
COPY --from=web --chown=1000:1000 /build/web/.next/static ./web/.next/standalone/.next/static
RUN useradd -m -u 1000 mentor && mkdir -p /app/data/videos && chown -R mentor:mentor /app/data
USER mentor
ENV PYTHONUNBUFFERED=1 NEXT_TELEMETRY_DISABLED=1 VRAG_DATA=/app/data
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=4)"
CMD ["python", "scripts/cloud-start.py"]
