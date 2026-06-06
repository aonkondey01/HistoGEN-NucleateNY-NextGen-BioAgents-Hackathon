#!/usr/bin/env bash
# Start HistoGen UI with Biohub protein structure proxy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI="$ROOT/ui"
VENV="$UI/.venv"

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -r "$UI/requirements.txt"
fi

exec "$VENV/bin/python" "$UI/protein_server.py"
