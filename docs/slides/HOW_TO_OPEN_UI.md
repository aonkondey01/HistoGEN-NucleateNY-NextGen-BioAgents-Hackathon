# HistoGEN — one UI

```bash
bash scripts/run_haiku_ui.sh
# → http://localhost:5173
```

Single Vite app: **20 TCGA patients**, **PHOENIX spatial RNA** heatmap (left), **H&E** thumbnail (center), UMAP + immune signatures (right).

If Cursor Ports fail:

```bash
bash scripts/start_public_ui.sh
```

Copy the printed `*.trycloudflare.com` URL — one link, one app.

Data lives in `ui/haiku-patient-explorer/public/data/`:
- `spatial_heatmap_TCGA-*.json` — PHOENIX readouts (from `demo/ui/`)
- `slides/*.thumbnail.png` — H&E previews
- `patients_embedding.json` — 20-patient UMAP

Regenerate:

```bash
python ui/haiku-patient-explorer/scripts/generate_representative_ui_data.py
```

`ui/index.html` is an old 4-panel prototype — **not used**. Do not start `protein_server` or port 8080.
