#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPLORER="$ROOT_DIR/ui/haiku-patient-explorer"
DEMO_UI="$ROOT_DIR/demo/ui"

cd "$EXPLORER"

# Wire demo JSON into Vite public/ (symlink when possible).
mkdir -p public
if [[ -d public/data && ! -L public/data ]]; then
  rm -rf public/data
fi
if [[ ! -e public/data ]]; then
  ln -sfn "$DEMO_UI" public/data
fi
if [[ ! -e public/demo ]]; then
  ln -sfn "$ROOT_DIR/demo" public/demo
fi

if [[ ! -d node_modules ]]; then
  npm install
fi

if [[ ! -f "$DEMO_UI/patients_embedding.json" ]]; then
  echo "Generating demo patient embedding JSON…"
  python3 scripts/generate_representative_ui_data.py
fi

echo ""
echo "=============================================="
echo "  HistoGEN Explorer  →  http://localhost:5173"
echo "  (demo mode — 20 TCGA patients)"
echo "=============================================="
echo ""
echo "Optional API/proxy: bash scripts/run_ui.sh  (port 8080)"
echo ""

npm run dev -- --host 0.0.0.0 --port 5173
