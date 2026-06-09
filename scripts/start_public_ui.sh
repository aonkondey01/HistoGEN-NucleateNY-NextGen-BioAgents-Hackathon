#!/usr/bin/env bash
# Public URL for HistoGEN when Cursor localhost port forwarding fails.
# Uses Cloudflare quick tunnel → no Ports panel needed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/scripts/build_explorer_static.sh"

# Start UI server in background if not already listening
if ! curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
  echo "Starting UI server on :8080…"
  tmux -f /exec-daemon/tmux.portal.conf has-session -t "=histogen-dashboard" 2>/dev/null || \
    tmux -f /exec-daemon/tmux.portal.conf new-session -d -s histogen-dashboard -c "$ROOT" -- "${SHELL:-zsh}" -l
  tmux -f /exec-daemon/tmux.portal.conf send-keys -t histogen-dashboard:0.0 \
    "cd $ROOT/ui && UI_HOST=0.0.0.0 python3 protein_server.py" C-m
  for _ in $(seq 1 20); do
    curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && break
    sleep 1
  done
fi

CF="${CF:-/tmp/cloudflared}"
if [[ ! -x "$CF" ]]; then
  curl -fsSL -o "$CF" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x "$CF"
fi

echo ""
echo "=============================================="
echo "  Opening public tunnel to port 8080…"
echo "=============================================="
echo ""
echo "  Dashboard:  <url>/"
echo "  Explorer:   <url>/explorer/"
echo "  Health:     <url>/health"
echo ""
echo "Waiting for trycloudflare.com URL…"
exec "$CF" tunnel --url http://127.0.0.1:8080 --no-autoupdate
