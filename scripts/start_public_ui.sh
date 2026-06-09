#!/usr/bin/env bash
# Public URL when Cursor localhost forwarding fails — single HistoGEN app on :5173
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF="${CF:-/tmp/cloudflared}"
[[ -x "$CF" ]] || { curl -fsSL -o "$CF" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x "$CF"; }

if ! curl -sf http://127.0.0.1:5173/ >/dev/null 2>&1; then
  tmux -f /exec-daemon/tmux.portal.conf has-session -t "=histogen-explorer" 2>/dev/null || \
    tmux -f /exec-daemon/tmux.portal.conf new-session -d -s histogen-explorer -c "$ROOT" -- "${SHELL:-zsh}" -l
  tmux -f /exec-daemon/tmux.portal.conf send-keys -t histogen-explorer:0.0 "bash $ROOT/scripts/run_haiku_ui.sh" C-m
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:5173/ >/dev/null 2>&1 && break; sleep 1; done
fi

echo "HistoGEN → waiting for trycloudflare.com URL…"
exec "$CF" tunnel --url http://127.0.0.1:5173 --no-autoupdate
