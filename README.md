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
  index.html              HistoGEN Advisor dashboard (only UI)
  protein_server.py       FastAPI: static UI + /api protein + PHOENIX + cohort figures
docs/slides/     Pitch deck assets (static .pptx + speaker notes)
```

## Quick start

### HistoGEN UI

```bash
bash scripts/run_ui.sh
# → http://localhost:8080
```

One app: **HistoGen Advisor** chat (protein structures + cohort figure plots), PHOENIX RNA viewer, 20-patient cluster graph. Demo data in `demo/`.

Public tunnel if needed: `bash scripts/start_public_ui.sh`

The bundled demo uses a stratified subset of **20 open-access TCGA lung diagnostic
H&E slides** (LUAD + LUSC). See `demo/README.md`.

```bash
bash scripts/demo/build_all.sh
```

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
general paths, required secrets, and GPU assumptions.

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
