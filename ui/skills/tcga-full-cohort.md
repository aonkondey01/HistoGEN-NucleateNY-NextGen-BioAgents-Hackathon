# TCGA lung (full cohort)

General-purpose scripts under `data/tcga_lung/` for the **full** open-access lung
diagnostic slide cohort (~1,053 slides, ~824 GB). Use `demo/` and `scripts/demo/`
for the 20-patient subset instead.

## Commands

```bash
cd data/tcga_lung
pip install -r requirements.txt
python3 -m py_compile download.py generate_manifest.py slide.py svs_to_zarr.sh

# Preview
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run --limit 3

# Pilot → light Zarr
bash fetch_three_light_zarr.sh
```

## Optional OpenSlide backend

```bash
sudo apt-get install -y openslide-tools
pip3 install openslide-python
```

## Gotchas

- Never commit `WSI/`, `*.svs`, or large zarr stores
- `generate_manifest.py` without `--out-dir` overwrites committed manifests
- Representative patient selection now writes to `demo/` via `select_representative_patients.py`
