# PEAT-Nucleate-BIoHack-2026

Hackathon workspace for **HistoGEN** — a clinical AI workflow that starts from
routine H&E, infers virtual spatial biology, retrieves similar patients, and
drafts a citation-backed molecular tumor board report.

The active model stack is **PHOENIX**, **GigaTIME**, and **Haiku** (patient
embedding similarity + agent chat).

## Stack

| Layer | Tool | Role |
|-------|------|------|
| Virtual spatial transcriptomics | [PHOENIX](https://huggingface.co/datasets/peng-lab/phoenix) | TCGA pan-cancer cell atlas (NEST embeddings, spatial coordinates) |
| Virtual multiplex protein (mIF) | [GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME) | H&E → 21-channel virtual mIF for TME phenotyping |
| Patient similarity & agent | **Haiku** | Embedding search, cluster assignment, clinical agent chat in the UI |

## Repository layout

```
demo/              20-patient TCGA demo cohort (WSI, PHOENIX, GigaTIME, Haiku, UI JSON)
data/
  tcga_lung/       Full-cohort manifests, download, slide IO, light Zarr
  phoenix/         PHOENIX atlas fetch + registration helpers
  gigatime/        GigaTIME weights fetch helper (gated HF)
scripts/demo/      One-command demo pipeline (GPU)
ui/
  index.html              HistoGEN 4-panel dashboard prototype
  haiku-patient-explorer/ Vite app — recurrence therapy predictions
  CURSOR_PROMPT.md        UI iteration brief for agents
docs/slides/     Pitch deck assets (static .pptx + speaker notes)
```

## Quick start

### Demo mode (20 patients, GPU recommended)

The bundled demo uses a stratified subset of **20 open-access TCGA lung diagnostic
H&E slides** (LUAD + LUSC). This is for local research demos only — not the full
~824 GB cohort.

```bash
# Full demo pipeline: WSI download → PHOENIX atlas → GigaTIME → Haiku → UI assets
bash scripts/demo/build_all.sh

# Launch dashboard (demo assets at /demo, API on :8080)
bash scripts/run_ui.sh

# Launch patient explorer (Vite on :5173, demo JSON symlinked from demo/ui/)
bash scripts/run_haiku_ui.sh
```

Demo mode is **on by default** in the UI. The dashboard loads case `TCGA-55-7815`
from the demo bundle instead of prompting for an SVS upload. Append `?demo=0` to
upload your own slide.

### General (full-cohort) scripts

**TCGA lung H&E** — manifests and download for all ~1,053 diagnostic slides:

```bash
cd data/tcga_lung
pip install -r requirements.txt
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3
```

**PHOENIX atlas** (~23 GB AnnData):

```bash
cd data/phoenix
pip install -r requirements.txt
python fetch.py
```

**GigaTIME weights** (gated — accept terms at [prov-gigatime/GigaTIME](https://huggingface.co/prov-gigatime/GigaTIME)):

```bash
export HF_TOKEN=hf_...
cd data/gigatime
pip install -r requirements.txt
python fetch.py
```

## Agents

Cloud and Cursor agents should read **`AGENTS.md`** first. It documents demo vs
general paths, required secrets, GPU assumptions, and agent skills under
`ui/skills/`.

## License notes

**HistoGEN and this repository are intended for non-commercial research and
education only.** Several bundled models and datasets carry non-commercial or
no-derivatives terms; do not use outputs in commercial products or clinical
decision-making without separate license review.

- **GigaTIME** — research-only, gated Hugging Face repo; **do not commit weights**
  or redistribute the checkpoint.
- **PHOENIX** — [CC-BY-NC-ND-4.0](https://huggingface.co/datasets/peng-lab/phoenix)
  (non-commercial, no derivatives).
- **TCGA** — The Cancer Genome Atlas provides open-access diagnostic H&E whole-slide
  images via the [NCI Genomic Data Commons (GDC)](https://portal.gdc.cancer.gov/).
  Slides are de-identified research specimens contributed under controlled-access
  policies; the **demo/** folder ships metadata and derived readouts for 20 lung
  cases only. Downloading the full lung cohort (~824 GB) is optional and handled
  by `data/tcga_lung/download.py`, not required to run the UI demo.
