# Opening the HistoGEN UI

Taylor's patient explorer (Vite app):

```bash
bash scripts/run_haiku_ui.sh
# → http://localhost:5173
```

In Cursor: **Ports** tab → forward **5173** → Open in Browser.

First run generates `public/data/patients_embedding.json` (~956 TCGA lung patients) if missing:

```bash
cd ui/haiku-patient-explorer
python3 scripts/generate_demo_data.py
```

## Static dashboard

`ui/index.html` — optional 4-panel prototype; open directly or serve with any static server.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ERR_CONNECTION_REFUSED` on localhost | Use Cursor Ports → forward 5173; or run locally on your machine |
| "Data load failed" | Re-run `generate_demo_data.py` |

Source branch: `cursor/treatment-benefit-ui-5384` (recurrence therapy predictions UI).
