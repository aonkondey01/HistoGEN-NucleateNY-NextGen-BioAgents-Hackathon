# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is

PEAT-Nucleate-BIoHack-2026 is a **Python CLI data toolkit** for downloading lung TCGA H&E diagnostic whole-slide images from the NCI Genomic Data Commons (GDC). There is no web server, database, Docker stack, or test/lint CI on `main`.

All scripts live under `data/tcga_lung/`. See `data/tcga_lung/README.md` for the full workflow.

### Services

| Component | Required? | Notes |
|-----------|-----------|-------|
| Python 3 | Yes | Stdlib only on `main` (`download.py`, `generate_manifest.py`) |
| GDC API (`api.gdc.cancer.gov`) | For live fetch/download | Open access; no API key or token |
| `gdc-client` | Optional | Auto-detected; falls back to built-in HTTP downloader |
| `slide.py` + pip deps | Optional | On branch `cursor/tcga-lung-he-download-2dbe` only |

No long-running services to start.

### Common commands

Run from `data/tcga_lung/`:

```bash
# Syntax check
python3 -m py_compile download.py generate_manifest.py

# Preview download (no network writes beyond manifest parse)
python3 download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3

# Pilot download (one slide ~400–700 MB)
python3 download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --limit 1

# Refresh manifests from GDC (writes to --out-dir; use /tmp to avoid dirtying the repo)
python3 generate_manifest.py --out-dir /tmp/tcga_manifest_test
```

### Slide IO (feature branch)

Branch `origin/cursor/tcga-lung-he-download-2dbe` adds `slide.py` and `requirements.txt` for thumbnails, crops, and tiling. After downloading at least one `.svs` into `WSI/`:

```bash
pip install -r requirements.txt
python slide.py info WSI/<file_id>/*.svs
python slide.py thumbnail WSI/<file_id>/*.svs
```

Optional system package for the preferred reader: `sudo apt-get install -y openslide-tools` then `pip install openslide-python`.

### Gotchas

- **Disk space**: full cohort is ~824 GB. Use `--dry-run` and `--limit N` for pilots. `WSI/` is gitignored.
- **No lint/test suite**: validate with `py_compile`, dry-run, and small pilot downloads.
- **Detached HEAD**: cloud VMs may checkout a specific commit; use `git checkout main` before branching.
- **Manifest regeneration**: `generate_manifest.py` without `--out-dir` overwrites committed manifests in the repo directory.
