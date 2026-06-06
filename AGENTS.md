# Agent instructions

## Cursor Cloud specific instructions

### HistoTME

The HistoTME setup requires Python venv support. If `.venv-histotme` is not
already available, install `python3.12-venv` first because the base image may
be missing `ensurepip`.

Prepare the HistoTME environment with:

```bash
bash scripts/setup_histotme.sh
```

This creates `.venv-histotme` for commands such as checkpoint downloads.

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
