# Opening the HistoGEN UI

## Dashboard (4-panel prototype)

```bash
bash scripts/run_ui.sh
# → http://localhost:8080
```

Demo mode is on by default — the center viewer loads the bundled demo H&E thumbnail.
Add `?demo=0` to upload your own slide.

## Patient explorer (Vite)

```bash
bash scripts/run_haiku_ui.sh
# → http://localhost:5173
```

In Cursor: **Ports** tab → open port **5173** or **8080**.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Demo H&E not loading | Run `bash scripts/run_ui.sh` so `/api/patients` and `/demo` are served |
| Missing embedding JSON | `python ui/haiku-patient-explorer/scripts/generate_representative_ui_data.py` |
| Empty spatial heatmaps | `python scripts/demo/build_ui_assets.py --skip-download` |

See `demo/README.md` for the full demo pipeline.
