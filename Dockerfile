# Baaki: one container, two processes.
#   uvicorn (FastAPI) on 127.0.0.1:8000, private to the container
#   next start on 0.0.0.0:$PORT, public; it proxies /api/* to the backend, so the phone only ever sees one origin
#
# Build:  docker build -t baaki --build-arg NEXT_PUBLIC_SITE_URL=https://your-host .
# Run:    docker run -p 3000:3000 -v baaki-data:/data --env-file .env.docker baaki
# Render (render.yaml) and Fly (fly.toml) build this file as is. Data lives on the volume at /data.

# --------------------------------------------------------------------------- 1. web build
FROM node:22-bookworm-slim AS web
WORKDIR /app/web
# web/.npmrc points the npm cache at B:/npm-cache (the dev laptop). An env var beats a project .npmrc,
# and .dockerignore leaves .npmrc out anyway.
ENV npm_config_cache=/tmp/npm \
    NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# Baked in at build time: the /api rewrite target, the public origin for link previews, the meter's interim step.
ARG BACKEND_URL=http://127.0.0.1:8000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_BAAKI_INTERIM_MS=4500
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_BAAKI_INTERIM_MS=$NEXT_PUBLIC_BAAKI_INTERIM_MS
# node_modules stay whole (no prune): `next start` loads next.config.ts, and keeping the dev tools avoids surprises.
RUN npm run build && rm -rf /tmp/npm .next/cache

# --------------------------------------------------------------------------- 2. runtime
FROM python:3.12-slim-bookworm AS runtime
# Node for `next start`: the official binary from the build stage (same Debian release, glibc and libstdc++ present).
COPY --from=web /usr/local/bin/node /usr/local/bin/node

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    PORT=3000 \
    DATABASE_URL=sqlite:////data/app.db \
    MEDIA_DIR=/data/media \
    TTS_CACHE_DIR=/data/tts_cache \
    AUDIO_TMP_DIR=/data/tmp \
    TMPDIR=/data/tmp

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
# Backend code, fonts and backend/seed_cache (pre-rendered demo voice clips + the noise-bench results).
# tts_cache looks in TTS_CACHE_DIR first and then backend/seed_cache/tts, so cached clips play on a cold start.
COPY backend/ backend/
COPY --from=web /app/web web/
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh && mkdir -p /data

# /data is the persistent disk (Render) or volume (Fly); without one it is ephemeral container storage.
EXPOSE 3000
CMD ["/app/start.sh"]
