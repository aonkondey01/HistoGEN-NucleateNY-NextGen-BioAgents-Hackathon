# Opening the HistoGEN UI

## Recommended: one port (8080)

Cursor **Ports forwarding often fails** for Cloud Agents (`ERR_CONNECTION_REFUSED`
on `localhost:5173` / `8080`). Avoid port 5173 entirely — serve both UIs from
8080:

```bash
bash scripts/run_all_ui.sh
```

| URL | UI |
|-----|-----|
| http://localhost:8080/ | Dashboard (4-panel) |
| http://localhost:8080/explorer/ | Patient explorer (static build) |
| http://localhost:8080/health | Server check (`{"status":"ok"}`) |

In Cursor: forward **8080 only** → Open in Browser.

## If localhost still refuses: public tunnel

No Ports panel needed — gives a `*.trycloudflare.com` link:

```bash
bash scripts/start_public_ui.sh
```

Copy the printed URL. Dashboard = `/`, explorer = `/explorer/`.

## Why port 5173 fails (diagnosis)

| Layer | What we checked | Result |
|-------|-----------------|--------|
| Vite on VM | `curl localhost:5173` | ✅ 200 — server fine |
| Dashboard on VM | `curl localhost:8080` | ✅ 200 — server fine |
| Your Mac `localhost:5173` | Browser | ❌ nothing listening **locally** |

**Root cause:** Cursor must tunnel VM port → your machine. If the tunnel is
**Disconnected** or never forwarded, your browser hits your own laptop’s
`localhost`, not the cloud VM. The app is not broken; the **proxy tunnel** is.

Port **5173** is extra fragile because it’s a dev-only Vite port — Cursor may
not auto-detect it. **8080** is slightly more reliable, and **static explorer
at `/explorer/`** removes the need for 5173 entirely.

## Legacy: Vite dev server (port 5173)

Only if you need hot reload while editing the explorer:

```bash
bash scripts/run_haiku_ui.sh
```

Requires working Ports forward for 5173.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ERR_CONNECTION_REFUSED` on localhost | Use `bash scripts/start_public_ui.sh` |
| Dashboard loads, explorer 404 | `bash scripts/build_explorer_static.sh` then restart UI |
| Demo H&E missing | Ensure `bash scripts/run_ui.sh` is running (not plain `http.server`) |
