# Agent instructions

## What this repo is

**HistoGEN** prototype for PEAT-Nucleate BioHack 2026. The pipeline is:

1. **TCGA lung H&E** — download / tile / light-Zarr (`data/tcga_lung/`)
2. **PHOENIX** — virtual spatial transcriptomics reference atlas (`data/phoenix/`)
3. **GigaTIME** — virtual mIF from H&E (`data/gigatime/`)
4. **Claude Haiku** — patient embedding similarity + vMTB agent chat (`ui/`)

**Do not** set up, document, or reference HistoTME. It is out of scope for this
project.

## Secrets (Cloud Agent)

| Secret | Required for | Notes |
|--------|----------------|-------|
| `HF_TOKEN` | GigaTIME weights | Gated repo; account must accept [prov-gigatime/GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME) terms |
| `HF_TOKEN` | PHOENIX (optional) | Public dataset; token only helps rate limits |
| Anthropic API key | Haiku in production UI | Not wired in static `ui/index.html` yet; mock chat only |

## Common commands

### TCGA lung slides (`data/tcga_lung/`)

```bash
cd data/tcga_lung
pip install -r requirements.txt

python3 -m py_compile download.py generate_manifest.py slide.py svs_to_zarr.py
python3 download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3

# Three-patient pilot → light Zarr (skips native 40× level)
bash fetch_three_light_zarr.sh
```

Optional slide IO backend:

```bash
sudo apt-get install -y openslide-tools
pip3 install openslide-python
```

### PHOENIX (`data/phoenix/`)

```bash
cd data/phoenix
pip install -r requirements.txt
python fetch.py --list
python fetch.py   # ~23 GB atlas download
```

### GigaTIME (`data/gigatime/`)

```bash
export HF_TOKEN=...
cd data/gigatime
pip install -r requirements.txt
python fetch.py
```

### UI (`ui/`)

- **Do not refactor** unless the user asks.
- Product name is **HistoGEN** (never SpatialMTB).
- `ui/index.html` — single-file HistoGEN prototype (vanilla HTML/CSS/JS).
- `ui/haiku-patient-explorer/` — Vite UMAP + heatmap demo; run via
  `bash scripts/run_haiku_ui.sh`.
- Read `ui/CURSOR_PROMPT.md` for layout, brand colors, and iteration priorities.
- **Haiku** — cluster assignment, similarity search, agent chat.
- **Phoenix** — virtual RNA / spatial cell-state reference (viewer mode).
- **GigaTIME** — virtual protein / mIF (viewer mode).

```bash
python3 -m http.server 8080 --directory ui          # static dashboard
bash scripts/run_haiku_ui.sh                        # Vite explorer on :5173
```

## UI content generation (agent reference)

Use this section to regenerate or extend mock UI content without reading every
source file. All data is synthetic unless wired to real pipeline outputs.

### Brand & layout (both UIs)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0d0f14` | Page background |
| `--surface` | `#13161e` | Panels, top bar |
| `--border` | `#232733` | Dividers |
| `--accent` | `#4f8ef7` | Logo, primary actions, RNA mode |
| `--accent2` | `#7c5cbf` | Secondary accent, Protein mode |
| `--green` | `#3ecf8e` | Success, confidence, alive OS |
| `--yellow` | `#f5c542` | Warnings |
| `--text` | `#e2e6f0` | Body text |
| `--muted` | `#6b7280` | Labels, placeholders |
| Font | Inter (Google Fonts) | All UI copy |

**HistoGEN dashboard grid** (`ui/index.html`):

```
grid-template-columns: 300px | 1fr | 340px
grid-template-rows: 56px topbar | 1fr content
```

Panels: (1) Agent Chat 300px left, (2) H&E / Spatial Viewer center,
(3) Patient Cluster & Clinical 340px right.

**Haiku Patient Explorer grid** (`ui/haiku-patient-explorer/`):

Three columns: TME spatial heatmap (left) · H&E slide viewer (center) ·
right stack (embedding scatter, patient card, immune profile bars, survival stub).

### HistoGEN dashboard — demo patient (`ui/index.html`)

Primary demo case (index patient for all panels):

| Field | Value |
|-------|-------|
| `caseId` | `TCGA-55-8512` |
| `subtype` | `LUAD` |
| `driverMutation` | `EGFR exon 19 del` |
| `tmeArchetype` | `Inflamed` |
| `overallSurvival` | `24.3 months (deceased)` |
| Haiku cluster | **Cluster 4** — Immune-Hot / EGFR-mutant LUAD |
| Confidence | **87%** (High) |
| Tags | TMB-High, PD-L1 ≥50%, EGFR Exon 19 del, Stage IIIA, Adenocarcinoma |

**Top bar:** logo `HistoGEN`, patient hover card (150 ms delay) with 5 fields +
80×80 canvas H&E thumbnail (pink tissue gradient mock).

**Nearest similar patients (Cluster 4):**

| case_id | meta | similarity |
|---------|------|------------|
| TCGA-55-7903 | EGFR del19 · PD-L1 60% | 94% |
| TCGA-55-8621 | EGFR del19 · TMB-H | 91% |
| TCGA-44-2659 | LUAD · Stage IIIA | 88% |

**Agent chat — welcome stubs (hard-coded HTML):**

1. *"Hi! I'm PEAT's clinical AI…"*
2. *"This slide shows elevated **EGFR** expression… hot TME phenotype."*

**Suggestion chips:** `What is the TME here?` · `Explain cluster assignment` ·
`Immunotherapy likelihood?` · `Key spatial patterns?`

**`agentReplies[]` rotation** (700 ms delay after user message):

```javascript
[
  "Based on the spatial embedding, this patient's TME shows a high degree of immune infiltration co-localised with EGFR-amplified regions — a pattern strongly predictive of response to combined EGFR-TKI + immunotherapy.",
  "Cluster 4 patients in our TCGA cohort had a median OS of 22.4 months on EGFR-TKI monotherapy vs 31.7 months with combination therapy. This patient's profile aligns with the responder sub-group.",
  "The PD-L1 expression you see overlaid on the H&E corresponds to regions with high CD8+ T-cell density — this is the immune-inflamed phenotype, which generally predicts better checkpoint inhibitor response.",
  "I'd flag the stromal FOXP3+ Tregs at the invasion margin — they may blunt the immune response. Consider checking the TIGIT co-inhibitory axis.",
]
```

**Agent voice:** clinical, direct, evidence-first. Cite trials when claiming
therapeutic benefit (`[KEYNOTE-048, 2019]`). Flag low confidence explicitly.
Never say "I think" — use *"The spatial pattern suggests…"* or *"Evidence from
similar patients indicates…"*. More sample stubs in `ui/CURSOR_PROMPT.md`.

**Viewer modalities:**

| Mode | Backend model | Gene/protein dropdown | Colorbar |
|------|---------------|----------------------|----------|
| H&E | raw WSI | disabled | hidden |
| RNA | Phoenix | enabled | shown |
| Protein | GigaTIME | enabled | shown |

**Gene/protein dropdown groups:**

- Top Genes: EGFR, TP53, KRAS, MYC, CDH1, VEGFA
- Immune Markers: CD8A, FOXP3, PD-L1 (CD274), TIGIT
- Proteins: p53, HER2, Ki-67, E-Cadherin

Drag-drop accepts `.svs` / `.tiff` / `.png` on viewer canvas (image preview only;
WSI needs render pipeline).

**"Derive Clinical Characteristics & Outcomes" button** toggles `#plots-area`
with three placeholders:

1. Kaplan–Meier Overall Survival · Cluster 4 vs rest
2. Treatment Response Rates · EGFR-TKI vs IO vs Chemo
3. UMAP Embedding · Patient cluster position

### Haiku Patient Explorer — data files

Regenerate static JSON:

```bash
cd ui/haiku-patient-explorer
pip install numpy umap-learn scikit-learn   # or use repo venv
python scripts/generate_demo_data.py
```

**Inputs:** `data/tcga_lung/slides_metadata.tcga_lung.json` (case list).

**Outputs:**

- `public/data/patients_embedding.json`
- `public/data/spatial_heatmap_demo.json`

#### `patients_embedding.json` schema

```json
{
  "meta": {
    "n_patients": "<int>",
    "source": "TCGA lung diagnostic slides + synthetic TME signature demo (Phoenix/GigaTIME)",
    "projection": "UMAP (or PCA fallback) on signature matrix",
    "archetypes": ["Immune Desert", "Immune Inflamed", "Myeloid/Treg-rich", "Stroma-high"],
    "drivers": ["EGFR", "KRAS G12C", "ALK", "WT"],
    "color_signatures": ["Treg", "Effector_cells", "Macrophages", "CAF", "MDSC", "T_cells", "Checkpoint_inhibition", "Angiogenesis"]
  },
  "patients": [
    {
      "case_id": "TCGA-XX-XXXX",
      "project_id": "TCGA-LUAD" | "TCGA-LUSC",
      "umap_x": "<float>",
      "umap_y": "<float>",
      "archetype": "<one of meta.archetypes>",
      "driver": "<one of meta.drivers>",
      "os_status": "alive" | "deceased",
      "signatures": { "<signature_name>": "<float>" }
    }
  ]
}
```

**Archetype assignment** (`generate_demo_data.py`): score from signature row —
Immune Desert (−Treg −Effector), Immune Inflamed (+Effector +T_cells),
Myeloid/Treg-rich (+Treg +Macrophages), Stroma-high (+CAF).

**Driver weights** (random, seed 42): EGFR 22%, KRAS G12C 13%, ALK 5%, WT 60%.
**OS:** ~58% alive (`rng.random() > 0.42`).

**UI color maps** (`src/main.js`):

| Archetype | Hex |
|-----------|-----|
| Immune Desert | `#4e79a7` |
| Immune Inflamed | `#e15759` |
| Myeloid/Treg-rich | `#f28e2b` |
| Stroma-high | `#76b7b2` |

| Driver | Hex |
|--------|-----|
| EGFR | `#b07aa1` |
| KRAS G12C | `#59a14f` |
| ALK | `#edc948` |
| WT | `#9c755f` |

OS: alive `#008080`, deceased `#6b7280`.

**Embedding scatter color-by options:** archetype · driver · signature · os_status.

#### `spatial_heatmap_demo.json` schema

```json
{
  "case_id": "<selected case>",
  "signature": "Treg",
  "tile_size": 256,
  "tiles": [
    { "x": "<int px>", "y": "<int px>", "Treg": 0.0, "Effector_cells": 0.0, "Macrophages": 0.0, "CAF": 0.0 }
  ],
  "note": "Demo spatial scores — replace with predict_spatial.py output"
}
```

48×48 tile grid (512 px spacing). Radial demo pattern: Treg high at center,
effector at periphery, macrophages along vertical axis, CAF from bottom.

**Patient card fields rendered:** case_id, project_id, archetype pill, driver pill,
os_status, UMAP coordinates.

**Survival panel:** demo bar (72% width if alive, 28% if deceased) — wire to
`data/tcga_lung/clinical_metadata.tcga_lung.csv` for real KM.

**Slide viewer:** hue from `hashHue(case_id)` CSS mock — replace with
`data/tcga_lung/slide.py thumbnail` when WSI files exist.

### Wiring real pipeline outputs (future)

| UI surface | Replace mock with |
|------------|-------------------|
| H&E viewer canvas | `data/tcga_lung/zarr/` light pyramid or `slide.py` tiles |
| RNA overlay | PHOENIX spatial expression from `data/phoenix/` |
| Protein overlay | GigaTIME virtual mIF from `data/gigatime/` |
| Cluster card + similar patients | Haiku embedding API over Phoenix+GigaTIME features |
| Agent chat | Anthropic Haiku API (not wired in static HTML yet) |
| `patients_embedding.json` | UMAP on real signature matrix from pipeline |
| Spatial heatmap JSON | GigaTIME / Phoenix per-tile scores |

### UI iteration priorities

See `ui/CURSOR_PROMPT.md` for the full prioritized backlog (vMTB report panel,
clinical note intake, minimap WSI viewer, radar chart, export PDF stub, etc.).
Keep `ui/index.html` as a single vanilla file unless explicitly asked to add a
build step. Chart libs allowed via CDN: Chart.js, Plotly.js, or D3.

## Gotchas

- **Disk:** full TCGA lung cohort ≈ 824 GB. Use `--dry-run`, `--limit N`, and
  pilot manifests. `WSI/`, `zarr/`, and model weights are gitignored.
- **No CI test suite** on `main` — validate with `py_compile`, dry-run downloads,
  and small pilots.
- **GigaTIME weights** must never be committed.
- **`generate_manifest.py`** without `--out-dir` overwrites committed manifests
  in `data/tcga_lung/`.
- **Branch naming** for agent PRs: `cursor/<descriptive-name>-0459`.

## What to commit vs ignore

| Commit | Ignore |
|--------|--------|
| Scripts, manifests, metadata CSV/JSON | `WSI/`, `*.svs`, `zarr/`, `*.zarr/` |
| UI HTML/CSS/JS | GigaTIME `model.pth`, PHOENIX `.h5ad` |
| Docs, speaker notes | Large downloaded atlases |
