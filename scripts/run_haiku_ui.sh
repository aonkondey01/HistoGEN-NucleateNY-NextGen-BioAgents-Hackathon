#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/ui/haiku-patient-explorer"
if [[ ! -d node_modules ]]; then
  npm install
fi
python3 scripts/generate_demo_data.py
echo ""
echo "Starting Haiku Patient Explorer at http://localhost:5173"
echo "In Cursor: open the Ports panel and click port 5173"
echo ""
npm run dev -- --host 0.0.0.0 --port 5173
