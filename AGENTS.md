# Agent instructions

## What this repo is

**HistoGEN** prototype for the Nucleate NY NextGen BioAgents Hackathon. The pipeline is:

1. **TCGA lung H&E** — download / tile / light-Zarr (`data/tcga_lung/` general; `demo/` for 20 patients)
2. **PHOENIX** — virtual spatial RNA inference on H&E (`data/phoenix/`); TCGA AnnData is demo-only
3. **GigaTIME** — virtual mIF from H&E (GPU inference)
4. **Haiku** — joint encoder of H&E + clinical text for patient embedding similarity (`demo/haiku/`, cluster graph in UI)
5. **HistoGen Advisor** — clinical agent chat in `ui/` (LLM layer; demo mock only — **not** the Haiku encoder)

**Nomenclature:** *Haiku* here is the project's multimodal patient encoder. It is
**not** Anthropic's Claude Haiku model. The Advisor chat may use a separate LLM in
production; do not conflate the two in docs or UI copy.

**Do not** set up, document, or reference HistoTME. It is out of scope.

**Product name is HistoGEN** (never SpatialMTB or vMTB).

**Branch policy:** all work merges to **`main`**. There is one UI (`ui/index.html` +
`ui/protein_server.py`). Do not add alternate front-ends, Vite explorers, or
second ports. See [`docs/UI.md`](docs/UI.md).

## Demo vs general paths

| Task | Demo (20 patients) | General (full cohort) |
|------|-------------------|----------------------|
| Patient list | `demo/representative_20_patients.json` | `data/tcga_lung/slides_metadata.tcga_lung.json` |
| WSI download | `scripts/demo/fetch_wsi.py` → `demo/WSI/` | `data/tcga_lung/download.py` → `data/tcga_lung/WSI/` |
| PHOENIX weights | `scripts/demo/fetch_phoenix.py` → `data/phoenix/` | `data/phoenix/fetch.py` |
| PHOENIX demo AnnData | `scripts/demo/fetch_demo_atlas.py` → `demo/phoenix/` | `data/phoenix/fetch_demo_atlas.py` |
| PHOENIX bundles | `scripts/demo/run_phoenix.py --demo-atlas` → `demo/data_package/` | `data/phoenix/inference.py` on your H&E |
| H&E registration | `data/phoenix/register_phoenix_to_he.py` (contour ICP + optical flow) | same |
| GigaTIME | `scripts/demo/run_gigatime.py` (GPU) | fetch weights only in `data/gigatime/` |
| Haiku embeddings | `scripts/demo/run_haiku.py` → `demo/haiku/` | N/A (encoder backend; not the chat LLM) |
| Cohort figures | `demo/visual_report/` | — |
| UI | `bash scripts/run_ui.sh` → `:8080` | same |

Path module: `demo/paths.py`. Config: `demo/config.json`.

**Assume the user has a CUDA GPU** for GigaTIME demo inference.

## Agent skills (`ui/skills/`)

Read the relevant skill before working in that area:

| Skill file | Use when |
|------------|----------|
| `protein-structure.md` | Biohub ESM Atlas / GigaTIME marker structures in chat |
| `cohort-visual-report.md` | Agent cohort figure knowledge base |

For pipeline topics without a skill file, read the matching script directory:
`scripts/demo/` (demo pipeline), `data/phoenix/` (weights + inference + registration),
`data/tcga_lung/` (full cohort), `data/gigatime/` (weights + inference).

## Secrets (Cloud Agent)

| Secret | Required for | Notes |
|--------|----------------|-------|
| `HF_TOKEN` | GigaTIME weights | Gated repo; accept [prov-gigatime/GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME) terms |
| `HF_TOKEN` | PHOENIX weights (optional) | Public model repo; token helps rate limits |
| `HF_TOKEN` | PHOENIX demo AnnData (optional) | `fetch_demo_atlas.py` only |
| Anthropic API key | HistoGen Advisor chat (production LLM) | Not wired in demo `ui/index.html`; mock chat only |
| `BIOHUB_API_KEY` | Protein structure viewer | Optional; demo cache in `ui/demo_cache/gigatime_structures/` |

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
cd data/phoenix && pip install -r requirements.txt
python fetch.py                    # model weights (~5 GB) — inference on your H&E
python inference.py --svs slide.svs --out-dir ./outputs/case
python fetch_demo_atlas.py         # demo-only TCGA AnnData (~23 GB)

python scripts/demo/fetch_phoenix.py
python scripts/demo/fetch_demo_atlas.py
python scripts/demo/run_phoenix.py              # GPU inference on demo WSIs
python scripts/demo/run_phoenix.py --demo-atlas   # or subset precomputed AnnData
```

### GigaTIME

```bash
export HF_TOKEN=...
cd data/gigatime && pip install -r requirements.txt && python fetch.py
python scripts/demo/run_gigatime.py           # GPU inference on demo WSIs
```

### UI

- **Only UI:** HistoGEN Advisor — `ui/index.html` + `ui/protein_server.py`
- Run: `bash scripts/run_ui.sh` → port **8080**
- Public tunnel: `bash scripts/start_public_ui.sh`
- Chat: protein structures (`/api/protein/structure`) + cohort figures (`/api/agent/cohort-figures`)
- Viewer: PHOENIX RNA uses **registered** thumbnail coords from `phoenix_registration/phoenix_cells_registered.csv`
- **Removed / do not restore:** Taylor Vite explorer, Emma spatial UI, `ui/haiku-patient-explorer/`, `demo/ui/`

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

Initial viewer load uses `TCGA-56-5898` for the H&E preview canvas.

### Viewer modalities

| Mode | Backend | Dropdown |
|------|---------|----------|
| H&E | demo WSI / thumbnail | disabled |
| RNA | PHOENIX (registered coords) | enabled |
| Protein | GigaTIME | enabled |

### Regenerate PHOENIX demo bundles (20 patients)

```bash
python scripts/demo/fetch_phoenix.py
python scripts/demo/fetch_demo_atlas.py
python scripts/demo/run_phoenix.py --demo-atlas
python scripts/demo/build_ui_assets.py --skip-download
```

## Gotchas

- **Disk:** full TCGA lung cohort ≈ 824 GB. Use `--dry-run`, `--limit N`, demo folder for UI.
- **PHOENIX gene summary CSV** uses column `mean_readout` (not `mean`); `ui/phoenix_data.py` handles both.
- **GigaTIME weights** must never be committed.
- **`generate_manifest.py`** without `--out-dir` overwrites committed manifests.
- **Non-commercial only** — PHOENIX NC-ND, GigaTIME research license; see README license notes.
- **One UI only** — do not reintroduce port 5173, `/explorer/`, or parallel Vite apps.

## What to commit vs ignore

| Commit | Ignore |
|--------|--------|
| Scripts, manifests, metadata CSV/JSON | `demo/WSI/`, `data/**/WSI/`, `*.svs`, `*.zarr/` |
| `demo/data_package/` per-patient bundles | `demo/phoenix/*.h5ad`, GigaTIME `model.pth`, `data/phoenix/weights/`, inference outputs |
| UI HTML/CSS/JS, cohort figures, protein cache JSON | Large downloaded AnnData / WSI |
