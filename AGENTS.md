# Agent instructions

## Cursor Cloud specific instructions

### HistoTME

The HistoTME setup requires Python venv support. If `.venv-histotme` is not
already available, install system packages first because the base image may be
missing `ensurepip` and OpenSlide:

```bash
sudo apt-get install -y python3.12-venv openslide-tools
```

Initialize the submodule, then prepare the HistoTME environment with:

```bash
git submodule update --init --recursive external/HistoTME
bash scripts/setup_histotme.sh
source .venv-histotme/bin/activate
```

This creates `.venv-histotme` for commands such as checkpoint downloads and
slide-deck generation (`python scripts/build_lung_tme_slide_deck.py`).

Gotcha: HistoTME pins `numpy<2`, while `data/tcga_lung/requirements.txt`
(zarr 3 / recent tifffile) wants `numpy>=2`. Keep TCGA stdlib scripts on
system `python3`; only install TCGA slide IO deps into `.venv-histotme` if you
accept pinning `numpy<2` (slide fallback path may still work for pilots).

### TCGA lung slide toolkit

PEAT-Nucleate-BIoHack-2026 includes a Python CLI data toolkit for downloading
lung TCGA H&E diagnostic whole-slide images from the NCI Genomic Data Commons
(GDC). All scripts live under `data/tcga_lung/`. See `data/tcga_lung/README.md`
for the full workflow.

| Component | Required? | Notes |
|-----------|-----------|-------|
| Python 3 | Yes | Stdlib for `download.py`, `generate_manifest.py` |
| GDC API (`api.gdc.cancer.gov`) | For live fetch/download | Open access; no API key |
| `gdc-client` | Optional | Auto-detected; falls back to built-in HTTP downloader |
| `slide.py` + pip deps | For slide IO/rendering | `pip install -r requirements.txt`; optional `openslide-tools` + `openslide-python` |

Run from `data/tcga_lung/`:

```bash
python3 -m py_compile download.py generate_manifest.py slide.py
python3 download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3
```

Slide IO setup (once per VM):

```bash
sudo apt-get install -y openslide-tools   # optional but preferred backend
pip3 install -r data/tcga_lung/requirements.txt openslide-python
```

`slide.py` auto-detects OpenSlide when installed; otherwise it falls back to
`tifffile` + `zarr`.

Gotchas:

- Full cohort is ~824 GB. Use `--dry-run` and `--limit N` for pilots. `WSI/` is gitignored.
- No lint/test suite on `main`: validate with `py_compile`, dry-run, and small pilot downloads.
- `generate_manifest.py` without `--out-dir` overwrites committed manifests in the repo directory.

### SpatialMTB UI and TCGA visual report

No build step. Serve locally for browser testing:

```bash
cd ui && python3 -m http.server 8080
cd data/tcga_lung/important_lung_genes/visual_report && python3 -m http.server 8081
```

Open `http://127.0.0.1:8080/index.html` (SpatialMTB mock dashboard) and
`http://127.0.0.1:8081/index.html` (committed lung-gene cohort report).
