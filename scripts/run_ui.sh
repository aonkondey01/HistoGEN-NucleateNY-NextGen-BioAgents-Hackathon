#!/usr/bin/env bash
# Start HistoGEN UI with Biohub protein structure proxy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI="$ROOT/ui"
VENV="$UI/.venv"

if [[ ! -d "$VENV" ]]; then
  if python3 -m venv "$VENV" 2>/dev/null; then
    "$VENV/bin/pip" install -r "$UI/requirements.txt"
  else
    echo "Note: python3-venv unavailable — using system Python"
    VENV=""
  fi
fi

if [[ -n "${VENV:-}" && -d "$VENV" ]]; then
  exec "$VENV/bin/python" "$UI/protein_server.py"
else
  exec python3 "$UI/protein_server.py"
fi
