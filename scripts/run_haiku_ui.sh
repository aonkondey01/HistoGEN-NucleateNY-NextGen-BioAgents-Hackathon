#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/ui/haiku-patient-explorer"
if [[ ! -d node_modules ]]; then
  npm install
fi
if [[ ! -f public/data/patients_embedding.json ]]; then
  echo "Generating patient data (first run only, ~30s)…"
  python3 scripts/generate_demo_data.py
fi
echo ""
echo "=============================================="
echo "  HistoGEN  →  http://localhost:5173"
echo "=============================================="
echo ""
echo "HOW TO OPEN:"
echo "  1. In Cursor: bottom panel → Ports → click 5173 → Open in Browser"
echo "  2. Or paste http://localhost:5173 into Chrome/Safari"
echo ""
echo "See docs/slides/HOW_TO_OPEN_UI.md for troubleshooting"
echo ""
npm run dev -- --host 0.0.0.0 --port 5173
