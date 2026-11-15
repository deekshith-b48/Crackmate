#!/usr/bin/env bash
# One command: build the web app if needed, then serve everything at http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d web/out ]; then
  (cd web && npm ci --no-audit --no-fund && npm run build)
fi
exec .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
