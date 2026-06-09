#!/usr/bin/env bash
# End-to-end demo pipeline for the 20-patient HistoGEN cohort (GPU machine).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== HistoGEN demo pipeline =="
echo "Repo: $ROOT"
echo ""

python3 scripts/demo/fetch_wsi.py "$@"
python3 scripts/demo/fetch_phoenix.py
python3 scripts/demo/run_gigatime.py "$@"
python3 scripts/demo/run_haiku.py "$@"
python3 scripts/demo/build_ui_assets.py --skip-download "$@"

echo ""
echo "Demo assets ready under demo/"
echo "  UI JSON  -> demo/ui/"
echo "  Haiku    -> demo/haiku/"
echo "  GigaTIME -> demo/gigatime/outputs/"
echo ""
echo "Start UI: bash scripts/run_ui.sh   (dashboard :8080)"
echo "          bash scripts/run_haiku_ui.sh (explorer :5173)"
