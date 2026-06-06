# PEAT-Nucleate-BIoHack-2026

Hackathon workspace for **HistoGEN** — a clinical AI workflow that starts from
routine H&E, infers virtual spatial biology, retrieves similar patients, and
drafts a citation-backed virtual molecular tumor board (vMTB) report.

The active model stack is **Phoenix**, **GigaTIME**, and **Claude Haiku** (no
HistoTME).

## Live UI (GitHub Pages)

**[Haiku Patient Explorer](https://aonkondey01.github.io/PEAT-Nucleate-BIoHack-2026/)** — interactive UMAP + spatial TME heatmap for 20 representative TCGA lung patients.

> **Pages must use the `gh-pages` branch**, not `main`. If you only see this README, go to **Settings → Pages → Deploy from branch → `gh-pages` / (root)**. See [`docs/slides/HOW_TO_OPEN_UI.md`](docs/slides/HOW_TO_OPEN_UI.md).

## Stack

| Layer | Tool | Role |
|-------|------|------|
| Virtual spatial transcriptomics | [PHOENIX](https://huggingface.co/datasets/peng-lab/phoenix) | TCGA pan-cancer cell atlas (NEST embeddings, spatial coordinates) |
| Virtual multiplex protein (mIF) | [GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME) | H&E → 21-channel virtual mIF for TME phenotyping |
| Patient similarity & agent | **Claude Haiku** | Embedding search, cluster assignment, vMTB chat in the UI |

## Repository layout

```
data/
  tcga_lung/     TCGA-LUAD/LUSC H&E manifests, download, slide IO, light Zarr
  phoenix/       PHOENIX atlas fetch helper
  gigatime/      GigaTIME weights fetch helper (gated HF)
ui/
  index.html              HistoGEN 4-panel dashboard prototype
  haiku-patient-explorer/ Vite app — recurrence therapy predictions (Taylor UI)
  CURSOR_PROMPT.md        UI iteration brief for agents
docs/slides/     Pitch deck assets (static .pptx + speaker notes)
```

## Quick start

### 1. TCGA lung H&E (data layer)

```bash
cd data/tcga_lung
pip install -r requirements.txt

# Preview cohort download
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3

# Pilot: three slides → light Zarr stores
bash fetch_three_light_zarr.sh
```

See `data/tcga_lung/README.md` for manifests, clinical metadata, and molecular
extracts.

### 2. PHOENIX atlas

```bash
cd data/phoenix
pip install -r requirements.txt
python fetch.py --list
python fetch.py    # default: tcga-atlas-nest-multi-cell-20x-discrete.h5ad (~23 GB)
```

### 3. GigaTIME weights

Gated — accept terms at [prov-gigatime/GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME), then:

```bash
export HF_TOKEN=hf_...
cd data/gigatime
pip install -r requirements.txt
python fetch.py
# or: bash fetch.sh
```

### 4. HistoGEN UI

**Static dashboard:** open `ui/index.html` in a browser (no build step). The right
panel uses **Haiku** for cluster assignment and similarity search; the center
viewer toggles H&E / virtual RNA (Phoenix) / virtual protein (GigaTIME).

**Haiku explorer (Vite):** Taylor's three-column UI — targeted vs immunotherapy benefit
if disease recurs, H&E placeholder, and UMAP patient embedding (~956 TCGA lung cases).

```bash
bash scripts/run_haiku_ui.sh
# → http://localhost:5173
# GitHub Pages: https://aonkondey01.github.io/PEAT-Nucleate-BIoHack-2026/
```

## Agents

Cloud and Cursor agents should read **`AGENTS.md`** first. It documents required
secrets, common commands, disk-space gotchas, and what not to commit.

## License notes

- **GigaTIME** — research-only, gated; do not commit weights.
- **PHOENIX** — [CC-BY-NC-ND-4.0](https://huggingface.co/datasets/peng-lab/phoenix).
- **TCGA** — open-access diagnostic slides via GDC; full cohort is ~824 GB.
