# HistoGEN demo cohort (20 patients)

Non-commercial research demo built from open-access **TCGA** diagnostic H&E slides
(LUAD + LUSC). This folder holds the representative 20-patient subset used by the
**HistoGEN Advisor** UI — not the full ~824 GB lung cohort.

## Layout

| Path | Purpose |
|------|---------|
| `representative_20_patients.json` | Selected case list + clinical metadata |
| `data_package/per_patient/` | Per-patient clinical, PHOENIX readouts, slide previews, registration |
| `genomic_data/` | MAF / CNV manifests and parsed tables for the 20 cases |
| `visual_report/` | Cohort summary figures for the agent knowledge base |
| `WSI/` | Downloaded diagnostic `.svs` files (gitignored) |
| `phoenix/` | PHOENIX atlas AnnData (~23 GB, gitignored) |
| `gigatime/outputs/` | Virtual mIF tiles per slide (gitignored) |
| `haiku/` | Patient embeddings (gitignored; not a separate UI) |

## One-command setup (GPU machine)

Requires `HF_TOKEN` (GigaTIME gate accepted) and a CUDA GPU.

```bash
bash scripts/demo/build_all.sh
```

Or step by step:

```bash
python scripts/demo/fetch_wsi.py
python scripts/demo/fetch_phoenix.py
python scripts/demo/extract_phoenix_bundles.py   # AnnData → CSV + contour/flow registration
python scripts/demo/run_gigatime.py
python scripts/demo/run_haiku.py
python scripts/demo/build_ui_assets.py           # thumbnails + registration refresh
```

Start the UI: `bash scripts/run_ui.sh` → http://localhost:8080

See [`docs/UI.md`](../docs/UI.md) for the single-UI policy and deprecated alternate front-ends.

## General (full-cohort) scripts

For manifests, metadata, and arbitrary cohort downloads use `data/tcga_lung/`,
`data/phoenix/fetch.py`, and `data/gigatime/fetch.py` instead of the demo helpers
above.
