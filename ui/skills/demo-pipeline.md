# Demo pipeline

End-to-end setup for the 20-patient HistoGEN demo on a **GPU machine**.

## When to use

- User asks to run the demo, fetch demo WSIs, or rebuild UI assets
- Cloud agent needs the representative cohort (not full 824 GB TCGA download)

## Layout

| Path | Contents |
|------|----------|
| `demo/representative_20_patients.json` | Case list + clinical metadata |
| `demo/data_package/per_patient/` | PHOENIX readouts, clinical JSON, slide previews |
| `demo/WSI/` | Downloaded `.svs` (gitignored) |
| `demo/phoenix/` | Atlas `.h5ad` (gitignored) |
| `demo/gigatime/outputs/` | Virtual mIF outputs (gitignored) |
| `demo/haiku/` | Embedding JSON from clinical + H&E |
| `demo/ui/` | Static JSON for Vite explorer |

Path helpers: `demo/paths.py` — import `BUNDLE_ROOT`, `WSI_DIR`, `atlas_path()`, etc.

## Commands

```bash
bash scripts/demo/build_all.sh              # full pipeline
python scripts/demo/fetch_wsi.py --limit 3  # pilot download
python scripts/demo/fetch_phoenix.py
python scripts/demo/run_gigatime.py         # requires CUDA + HF weights
python scripts/demo/run_haiku.py
python scripts/demo/build_ui_assets.py --skip-download
```

## UI wiring

- `DEMO_MODE=1` (default) in `ui/.env` — dashboard loads demo case via `/api/patients/{caseId}`
- Explorer symlinks `demo/ui` → `public/data` in `scripts/run_haiku_ui.sh`
- Static assets served at `/demo` by `ui/protein_server.py`

## Default demo case

`TCGA-55-7815` (LUAD, non-smoker stratum) — see `demo/config.json`.
