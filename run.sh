#!/usr/bin/env bash
# One command: build the web app if needed, then serve everything at http://127.0.0.1:8000
# Port 8000 taken? Run:  CRACKMATE_PORT=8001 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d web/out ]; then
  (cd web && npm ci --no-audit --no-fund && npm run build)
fi
exec .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port "${CRACKMATE_PORT:-8000}"
