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
