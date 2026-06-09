# HistoGEN demo cohort (20 patients)

Non-commercial research demo built from open-access **TCGA** diagnostic H&E slides
(LUAD + LUSC). This folder holds the representative 20-patient subset used by the
UI and agent skills — not the full ~824 GB lung cohort.

## Layout

| Path | Purpose |
|------|---------|
| `representative_20_patients.json` | Selected case list + clinical metadata |
| `data_package/per_patient/` | Per-patient clinical, PHOENIX readouts, slide previews |
| `genomic_data/` | MAF / CNV manifests and parsed tables for the 20 cases |
| `visual_report/` | Cohort summary figures for the agent knowledge base |
| `WSI/` | Downloaded diagnostic `.svs` files (gitignored) |
| `phoenix/` | PHOENIX atlas AnnData (~23 GB, gitignored) |
| `gigatime/outputs/` | Virtual mIF tiles per slide (gitignored) |
| `haiku/` | Patient embeddings + clinical-note features (gitignored) |
| `ui/` | Static JSON consumed by the Vite explorer |

## One-command setup (GPU machine)

Requires `HF_TOKEN` (GigaTIME gate accepted) and a CUDA GPU.

```bash
bash scripts/demo/build_all.sh
```

Or step by step:

```bash
# 1. Download 20 diagnostic WSIs
python scripts/demo/fetch_wsi.py

# 2. PHOENIX atlas AnnData
python scripts/demo/fetch_phoenix.py

# 3. GigaTIME weights + virtual mIF inference
python scripts/demo/run_gigatime.py

# 4. Haiku embeddings from H&E + clinical notes
python scripts/demo/run_haiku.py

# 5. UI assets (thumbnails, spatial heatmaps, embedding JSON)
python scripts/demo/build_ui_assets.py
```

## General (full-cohort) scripts

For manifests, metadata, and arbitrary cohort downloads use `data/tcga_lung/`,
`data/phoenix/fetch.py`, and `data/gigatime/fetch.py` instead of the demo helpers
above.
