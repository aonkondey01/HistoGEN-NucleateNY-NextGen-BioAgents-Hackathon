# HistoGEN UI

There is **one** user-facing application: the **HistoGEN Advisor** dashboard.

```bash
bash scripts/run_ui.sh
# → http://localhost:8080
```

| File | Role |
|------|------|
| `ui/index.html` | Single-page dashboard (chat, viewer, cluster graph) |
| `ui/protein_server.py` | FastAPI server: static UI + protein + PHOENIX + cohort APIs |
| `scripts/run_ui.sh` | Start the Advisor |
| `scripts/start_public_ui.sh` | Cloudflare quick tunnel when localhost forwarding fails |

## PHOENIX RNA in the viewer

RNA overlays use per-patient bundles under `demo/data_package/per_patient/{caseId}/`:

1. **`phoenix_cells.csv`** — extracted from the PHOENIX AnnData atlas (`demo/phoenix/*.h5ad`)
2. **`phoenix_registration/phoenix_cells_registered.csv`** — contour ICP + optical-flow warp onto the H&E thumbnail ([`data/phoenix/registration.py`](../data/phoenix/registration.py), commit `86c0e7a`)

Build or refresh bundles:

```bash
python scripts/demo/fetch_phoenix.py
python scripts/demo/extract_phoenix_bundles.py
```

The UI server can also extract on first request when the atlas is present but CSVs are missing.

## Deprecated alternate UIs (do not restore)

These branches/PRs shipped **superseded** front-ends. They are not maintained:

| Branch / area | What it was |
|---------------|-------------|
| `cursor/treatment-benefit-ui-5384` | Taylor Vite recurrence-therapy explorer (~956 patients, port 5173) |
| `cursor/representative-20-ui-assets-c9eb` | Emma spatial heatmap explorer |
| `ui/haiku-patient-explorer/` | Removed from `main` — Vite + fake KM curves |
| `demo/ui/` | Removed — static JSON for the Emma explorer |

Use **HistoGEN Advisor only**. Do not add second URLs, `/explorer/` mounts, or parallel Vite apps.
