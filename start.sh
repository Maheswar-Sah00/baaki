#!/bin/sh
# Container entrypoint: FastAPI on 127.0.0.1:8000 (private), then Next on 0.0.0.0:$PORT (public).
# The backend seeds the demo story itself on first boot when the database is empty (ensure_seeded in the
# app's startup), so this script does not seed.
set -eu

PORT="${PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

# Links Baaki writes into messages: PUBLIC_BASE_URL if set, else the platform's own public URL.
if [ -z "${PUBLIC_BASE_URL:-}" ]; then
  if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
    PUBLIC_BASE_URL="$RENDER_EXTERNAL_URL"
  elif [ -n "${FLY_APP_NAME:-}" ]; then
    PUBLIC_BASE_URL="https://${FLY_APP_NAME}.fly.dev"
  fi
  if [ -n "${PUBLIC_BASE_URL:-}" ]; then export PUBLIC_BASE_URL; fi
fi

# Data folders on the persistent disk (the SQLite file's folder too).
for d in "${MEDIA_DIR:-/data/media}" "${TTS_CACHE_DIR:-/data/tts_cache}" "${AUDIO_TMP_DIR:-/data/tmp}"; do
  mkdir -p "$d"
done
case "${DATABASE_URL:-}" in
  sqlite:////*) mkdir -p "$(dirname "/${DATABASE_URL#sqlite:////}")" ;;
esac

cd /app
echo "start.sh: backend on 127.0.0.1:${BACKEND_PORT}"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# Wait for /health (first boot also creates the tables and seeds the demo story).
python - "$BACKEND_PORT" "$BACKEND_PID" <<'PY'
import os, sys, time, urllib.request
port, pid = sys.argv[1], int(sys.argv[2])
deadline = time.time() + 120
while time.time() < deadline:
    try:
        os.kill(pid, 0)
    except OSError:
        sys.exit("start.sh: backend exited during startup (see the log above)")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            if r.status == 200:
                print("start.sh: backend healthy", flush=True)
                sys.exit(0)
    except Exception:
        pass
    time.sleep(1)
sys.exit("start.sh: backend not healthy after 120 s")
PY

echo "start.sh: web on 0.0.0.0:${PORT}"
cd /app/web
exec node node_modules/next/dist/bin/next start -H 0.0.0.0 -p "$PORT"
