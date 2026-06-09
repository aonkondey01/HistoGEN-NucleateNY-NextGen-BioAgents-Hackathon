#!/usr/bin/env bash
# One port for everything: dashboard + built explorer + demo API.
# Avoids relying on Cursor forwarding port 5173 (Vite dev server).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/scripts/build_explorer_static.sh"
bash "$ROOT/scripts/run_ui.sh"
