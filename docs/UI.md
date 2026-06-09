# HistoGEN UI

There is **one** user-facing application: the **HistoGEN Advisor** dashboard.

```bash
bash scripts/run_ui.sh
# → http://localhost:8080
```

**Panels:**

- **Left** — HistoGen Advisor chat (protein structures, embedded cohort figures)
- **Center** — H&E + PHOENIX RNA overlay + protein mode
- **Right** — 20-patient cluster graph, similar patients, clinical tags

Demo data: `demo/` (PHOENIX bundles, visual report figures, per-patient bundles).

| File | Role |
|------|------|
| `ui/index.html` | Single-page dashboard (chat, viewer, cluster graph) |
| `ui/protein_server.py` | FastAPI server: static UI + protein + PHOENIX + cohort APIs |
| `scripts/run_ui.sh` | Start the Advisor |
| `scripts/start_public_ui.sh` | Cloudflare quick tunnel when localhost forwarding fails |

## PHOENIX RNA in the viewer

RNA overlays use per-patient bundles under `demo/data_package/per_patient/{caseId}/`:

1. **`phoenix_cells.csv`** — from PHOENIX inference or demo TCGA AnnData subset (`demo/phoenix/*.h5ad`)
2. **`phoenix_registration/phoenix_cells_registered.csv`** — contour ICP + optical-flow warp onto the H&E thumbnail ([`data/phoenix/registration.py`](../data/phoenix/registration.py), commit `86c0e7a`)

Build or refresh bundles:

```bash
python scripts/demo/fetch_phoenix.py
python scripts/demo/fetch_demo_atlas.py
python scripts/demo/run_phoenix.py --demo-atlas
```

The UI server can also extract on first request when demo AnnData is present but CSVs are missing.

## Deprecated alternate UIs (do not restore)

These front-ends were removed from the repo. **Do not reintroduce them:**

| Area | What it was |
|------|-------------|
| `ui/haiku-patient-explorer/` | Taylor Vite recurrence-therapy explorer (~956 patients, port 5173) |
| `demo/ui/` | Emma spatial heatmap JSON for a second explorer |
| `/explorer/` mount | Served alternate dashboard on the same server |

Use **HistoGEN Advisor only** on port **8080**. Do not add second URLs or parallel Vite apps.
