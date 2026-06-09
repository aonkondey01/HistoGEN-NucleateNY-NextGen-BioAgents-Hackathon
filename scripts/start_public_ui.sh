#!/usr/bin/env bash
# Public URL for HistoGEN Advisor when Cursor localhost forwarding fails.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF="${CF:-/tmp/cloudflared}"
[[ -x "$CF" ]] || { curl -fsSL -o "$CF" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x "$CF"; }

if ! curl -sf http://127.0.0.1:8080/ >/dev/null 2>&1; then
  tmux -f /exec-daemon/tmux.portal.conf has-session -t "=histogen-dashboard" 2>/dev/null || \
    tmux -f /exec-daemon/tmux.portal.conf new-session -d -s histogen-dashboard -c "$ROOT" -- "${SHELL:-zsh}" -l
  tmux -f /exec-daemon/tmux.portal.conf send-keys -t histogen-dashboard:0.0 "bash $ROOT/scripts/run_ui.sh" C-m
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8080/ >/dev/null 2>&1 && break; sleep 1; done
fi

echo "HistoGEN Advisor → waiting for trycloudflare.com URL…"
exec "$CF" tunnel --url http://127.0.0.1:8080 --no-autoupdate
