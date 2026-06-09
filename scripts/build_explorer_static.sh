#!/usr/bin/env bash
# Build the patient explorer as static files served at http://localhost:8080/explorer/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXPLORER="$ROOT/ui/haiku-patient-explorer"
DEMO_UI="$ROOT/demo/ui"

cd "$EXPLORER"
mkdir -p public
if [[ ! -e public/data ]]; then ln -sfn "$DEMO_UI" public/data; fi
if [[ ! -e public/demo ]]; then ln -sfn "$ROOT/demo" public/demo; fi

if [[ ! -d node_modules ]]; then npm install; fi
if [[ ! -f "$DEMO_UI/patients_embedding.json" ]]; then
  python3 scripts/generate_representative_ui_data.py
fi

EXPLORER_BASE=/explorer/ npm run build
echo ""
echo "Built explorer → $EXPLORER/dist"
echo "Serve with: bash scripts/run_ui.sh"
echo "Open:       http://localhost:8080/explorer/"
