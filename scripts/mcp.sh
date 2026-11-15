#!/usr/bin/env bash
# Starts the CrackMate MCP server (stdio) for Claude, Codex or any MCP host. Sets itself up on first run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -x .venv/bin/python ]; then
  PY="$(command -v python3.13 || command -v python3)"
  echo "CrackMate: first run, installing (about a minute)..." >&2
  "$PY" -m venv .venv >&2
  .venv/bin/python -m pip install -q -r requirements.txt -r requirements-api.txt >&2
fi
# Installed as a plugin: keep your data outside the plugin folder so updates never erase it.
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  mkdir -p "$HOME/.crackmate"
  export CRACKMATE_DB="${CRACKMATE_DB:-$HOME/.crackmate/preparation.sqlite3}"
  export CRACKMATE_REPOS="${CRACKMATE_REPOS:-$HOME/.crackmate/repos}"
fi
exec .venv/bin/python -m crackmate mcp
