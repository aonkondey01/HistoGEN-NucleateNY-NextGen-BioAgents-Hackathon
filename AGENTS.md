# Agent instructions

## What this repo is

**HistoGEN** prototype for PEAT-Nucleate BioHack 2026. The pipeline is:

1. **TCGA lung H&E** — download / tile / light-Zarr (`data/tcga_lung/` general; `demo/` for 20 patients)
2. **PHOENIX** — virtual spatial transcriptomics reference atlas
3. **GigaTIME** — virtual mIF from H&E (GPU inference)
4. **Haiku** — patient embedding similarity + clinical agent chat (`ui/`)

**Do not** set up, document, or reference HistoTME. It is out of scope.

**Product name is HistoGEN** (never SpatialMTB or vMTB).

## Demo vs general paths

| Task | Demo (20 patients) | General (full cohort) |
|------|-------------------|----------------------|
| Patient list | `demo/representative_20_patients.json` | `data/tcga_lung/slides_metadata.tcga_lung.json` |
| WSI download | `scripts/demo/fetch_wsi.py` → `demo/WSI/` | `data/tcga_lung/download.py` → `data/tcga_lung/WSI/` |
| PHOENIX atlas | `scripts/demo/fetch_phoenix.py` → `demo/phoenix/` | `data/phoenix/fetch.py` |
| GigaTIME | `scripts/demo/run_gigatime.py` (GPU) | fetch weights only in `data/gigatime/` |
| Haiku embeddings | `scripts/demo/run_haiku.py` → `demo/haiku/` | N/A (mock in UI) |
| Cohort figures | `demo/visual_report/` | — |
| Per-patient bundles | `demo/data_package/per_patient/` | — |

Path module: `demo/paths.py`. Config: `demo/config.json`.

**Assume the user has a CUDA GPU** for GigaTIME demo inference.

## Agent skills (`ui/skills/`)

Read the relevant skill before working in that area:

| Skill file | Use when |
|------------|----------|
| `demo-pipeline.md` | Demo setup, `build_all.sh`, demo UI assets |
| `tcga-full-cohort.md` | Full GDC manifests, 824 GB cohort download |
| `phoenix-atlas.md` | Atlas fetch, extract_slide_readouts, registration |
| `gigatime-inference.md` | HF weights, GPU virtual mIF |
| `haiku-embeddings.md` | Patient embeddings, explorer JSON |
| `protein-structure.md` | Biohub ESM Atlas / GigaTIME marker structures |
| `cohort-visual-report.md` | Agent cohort figure knowledge base |

## Secrets (Cloud Agent)

| Secret | Required for | Notes |
|--------|----------------|-------|
| `HF_TOKEN` | GigaTIME weights | Gated repo; accept [prov-gigatime/GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME) terms |
| `HF_TOKEN` | PHOENIX (optional) | Public dataset; token helps rate limits |
| Anthropic API key | Haiku agent (production) | Not wired in static `ui/index.html`; mock chat only |
| `BIOHUB_API_KEY` | Protein structure viewer | Optional; demo cache in `ui/demo_cache/` |

## Common commands

### Demo pipeline (GPU)

```bash
bash scripts/demo/build_all.sh
bash scripts/run_ui.sh          # HistoGEN Advisor :8080
```

### TCGA lung slides (general)

```bash
cd data/tcga_lung
pip install -r requirements.txt
python3 -m py_compile download.py generate_manifest.py slide.py svs_to_zarr.py
python3 download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3
bash fetch_three_light_zarr.sh
```

### PHOENIX

```bash
python scripts/demo/fetch_phoenix.py          # demo atlas → demo/phoenix/
cd data/phoenix && python fetch.py            # general / legacy atlas path
```

### GigaTIME

```bash
export HF_TOKEN=...
cd data/gigatime && pip install -r requirements.txt && python fetch.py
python scripts/demo/run_gigatime.py           # GPU inference on demo WSIs
```

### UI

- **Only UI:** HistoGEN Advisor dashboard — `ui/index.html` + `ui/protein_server.py`
- Run: `bash scripts/run_ui.sh` → port **8080**
- Chat embeds **protein structures** (`/api/protein/structure`) and **cohort figures** (`/api/agent/cohort-figures`)
- Demo data: `demo/` (20 patients, PHOENIX bundles, `demo_cache/gigatime_structures/`)
- **Removed:** `ui/haiku-patient-explorer/` (Taylor/Emma Vite alternates)

```bash
bash scripts/run_ui.sh
```

## UI content generation (agent reference)

### Brand & layout

| Token | Value |
|-------|-------|
| `--bg` | `#0d0f14` |
| `--surface` | `#13161e` |
| `--border` | `#232733` |
| `--accent` | `#4f8ef7` |
| `--accent2` | `#7c5cbf` |
| `--green` | `#3ecf8e` |
| Font | Inter |

**Dashboard grid:** 300px HistoGen Advisor chat | 1fr H&E/RNA/Protein viewer | 340px cluster + clinical.

Chat embeds **protein structure cards** (ESM Atlas cache) and **cohort figure plots** (visual report PNGs).

### Demo patient (dashboard default)

| Field | Value |
|-------|-------|
| `caseId` | `TCGA-55-7815` |
| Source | `demo/data_package/per_patient/TCGA-55-7815/` |

Set `?demo=0` on the dashboard URL to enable SVS drag-drop upload.

### Viewer modalities

| Mode | Backend | Dropdown |
|------|---------|----------|
| H&E | demo WSI / thumbnail | disabled |
| RNA | PHOENIX | enabled |
| Protein | GigaTIME | enabled |

### Regenerate demo UI assets (20 patients)

```bash
python scripts/demo/build_ui_assets.py --skip-download
```

## Gotchas

- **Disk:** full TCGA lung cohort ≈ 824 GB. Use `--dry-run`, `--limit N`, demo folder for UI.
- **`data/phoenix/cohort.zarr` removed** — optional Zarr goes to `demo/phoenix/cohort.zarr`.
- **GigaTIME weights** must never be committed.
- **`generate_manifest.py`** without `--out-dir` overwrites committed manifests.
- **Non-commercial only** — PHOENIX NC-ND, GigaTIME research license; see README license notes.
- **Branch naming** for agent PRs: `cursor/<descriptive-name>-50bd`.

## What to commit vs ignore

| Commit | Ignore |
|--------|--------|
| Scripts, manifests, metadata CSV/JSON | `demo/WSI/`, `data/**/WSI/`, `*.svs`, `*.zarr/` |
| `demo/data_package/` small bundles | `demo/phoenix/*.h5ad`, GigaTIME `model.pth` |
| UI HTML/CSS/JS, `demo/ui/*.json` | Large atlases, inference outputs |
