FROM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS web
WORKDIR /build/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY web/package*.json ./
RUN --mount=type=secret,id=build_ca if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Assemble application assets without repeatedly copying the FFmpeg runtime layer.
FROM scratch AS bundle
COPY vrag /app/vrag
COPY config /app/config
COPY scripts/cloud-start.py /app/scripts/cloud-start.py
COPY --from=web /build/web/.next/standalone /app/web/.next/standalone
COPY --from=web /build/web/.next/static /app/web/.next/standalone/.next/static
COPY --from=web /build/web/public /app/web/.next/standalone/public

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime
WORKDIR /app
COPY requirements-runtime.txt ./
RUN --mount=type=secret,id=build_ca \
    export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY"; \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates libatomic1 ffmpeg age && \
    pip install --no-cache-dir -r requirements-runtime.txt && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -u 1000 mentor && mkdir -p /app/data/videos /app/work && chown -R mentor:mentor /app/data /app/work
COPY --from=web /usr/local/bin/node /usr/local/bin/node
COPY --from=bundle --chown=1000:1000 /app /app
USER mentor
ENV PYTHONUNBUFFERED=1 NEXT_TELEMETRY_DISABLED=1 VRAG_DATA=/app/work/data VM_STATE_DIR=/app/work/state
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=4)"
CMD ["python", "scripts/cloud-start.py"]
