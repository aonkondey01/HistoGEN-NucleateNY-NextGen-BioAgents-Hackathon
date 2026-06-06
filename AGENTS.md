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
- `ui/haiku-patient-explorer/` — Taylor's Vite UI (recurrence therapy predictions);
  run via `bash scripts/run_haiku_ui.sh`.
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

**HistoGEN Explorer grid** (`ui/haiku-patient-explorer/` — Taylor UI):

Three columns: **Recurrence therapy predictions** (left) · **H&E slide placeholder**
(center) · **Right stack** (UMAP embedding, patient card, immune signature bars,
survival stub).

Header brand: **HistoGEN** + logo (`public/logo.png`). Color-by dropdown options:
targeted @ recurrence · IO @ recurrence · preferred at recurrence · driver ·
archetype · prior treatment class · observed response · stage.

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

### HistoGEN Explorer — data files (Taylor UI)

Regenerate static JSON:

```bash
cd ui/haiku-patient-explorer
pip install pandas numpy umap-learn scikit-learn
python scripts/generate_demo_data.py
```

**Inputs:**

- `data/tcga_lung/slides_metadata.tcga_lung.json` — case list
- `data/tcga_lung/patient_metadata.tcga_lung.json` — clinical fields
- `data/tcga_lung/important_lung_genes/important_mutations.tcga_lung.csv` — drivers
- Optional: `external/HistoTME/example_data/pantcga_tme_signatures.csv` (falls back
  to synthetic signatures if missing)

**Output:** `public/data/patients_embedding.json` (~956 patients)

#### `patients_embedding.json` schema (Taylor)

```json
{
  "meta": {
    "n_patients": 956,
    "source": "TCGA lung + TME signatures + recurrence therapy predictions",
    "prediction_scenario": "Targeted vs immunotherapy benefit if disease recurs",
    "projection": "UMAP on TME signature scores",
    "archetypes": ["Immune Desert", "Immune Inflamed", "Myeloid/Treg-rich", "Stroma-high"],
    "color_signatures": ["Treg", "Effector_cells", "Macrophages", "CAF", "MDSC", "T_cells", "Checkpoint_inhibition", "Angiogenesis"],
    "treatment_categories": ["Chemotherapy", "Pharmaceutical", "..."],
    "benefit_labels": ["Likely benefit", "Uncertain benefit", "Unlikely benefit"],
    "recurrence_modalities": ["targeted_therapy", "immunotherapy"]
  },
  "patients": [{
    "case_id": "TCGA-XX-XXXX",
    "project_id": "TCGA-LUAD",
    "umap_x": 0.0, "umap_y": 0.0,
    "archetype": "Immune Inflamed",
    "driver": "EGFR",
    "histology": "Adenocarcinoma, NOS",
    "stage": "Stage IIIA",
    "smoking": "...",
    "os_status": "alive",
    "signatures": { "Treg": 0.0, "...": 0.0 },
    "treatment": { "category": "Pharmaceutical", "agents": [], "disease_response": "..." },
    "clinical": { "vital_status": "Alive", "overall_survival_days": 900 },
    "recurrence_predictions": {
      "scenario": "If disease recurs",
      "targeted_therapy": { "score": 85, "label": "Likely benefit", "recommended_regimen": "...", "reasons": [] },
      "immunotherapy": { "score": 62, "label": "Uncertain benefit", "recommended_regimen": "...", "reasons": [] },
      "preferred_at_recurrence": "Targeted therapy first"
    }
  }]
}
```

**Recurrence prediction heuristics** (`generate_demo_data.py`):

| Modality | Main inputs |
|----------|-------------|
| Targeted @ recurrence | EGFR, ALK, KRAS G12C, MET, BRAF drivers |
| Immunotherapy @ recurrence | Archetype + effector/T-cell/checkpoint signatures; penalize Treg/MDSC |
| Preferred | Compare scores; both &lt; 50 → combination/trial |

**Left panel copy:** targeted therapy score + suggested agents (e.g. Osimertinib),
IO score + regimen, preferred approach, prior treatment as context only.

### Wiring real pipeline outputs (future)

| UI surface | Replace mock with |
|------------|-------------------|
| H&E viewer canvas | `data/tcga_lung/zarr/` light pyramid or `slide.py` tiles |
| RNA overlay | PHOENIX spatial expression from `data/phoenix/` |
| Protein overlay | GigaTIME virtual mIF from `data/gigatime/` |
| Cluster card + similar patients | Haiku embedding API over Phoenix+GigaTIME features |
| Agent chat | Anthropic Haiku API (not wired in static HTML yet) |
| `patients_embedding.json` | UMAP + recurrence predictions from `generate_demo_data.py` |

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
