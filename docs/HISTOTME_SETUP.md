# HistoTME setup

This workspace tracks the upstream HistoTME code as a git submodule at
`external/HistoTME`.

HistoTME can run in this repo once three local assets exist:

1. Python dependencies from the HistoTME package.
2. Whole-slide image embeddings in HDF5 format with `coords` and `features`.
3. Gated HistoTMEv2 checkpoints from Hugging Face.

## 1. Initialize the code and Python environment

```bash
git submodule update --init --recursive
./scripts/setup_histotme.sh
source .venv-histotme/bin/activate
```

The setup script installs `external/HistoTME` in editable mode and adds
`huggingface_hub` for checkpoint downloads.

## 2. Get slides and generate embeddings

The TCGA lung diagnostic H&E manifest is already committed under
`data/tcga_lung`.

Preview or download a small pilot:

```bash
cd data/tcga_lung
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --limit 3
```

Full TCGA lung download is about 824 GB:

```bash
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --workers 8
```

After slides are present, create HDF5 patch embeddings using either:

- HistoTME preprocessing scripts in `external/HistoTME/data_preprocessing`.
- Trident for SVS slide tiling and foundation-model feature extraction.

The inference scripts expect each HDF5 file to contain:

```text
coords: tile x/y coordinates
features: foundation-model embeddings
```

Foundation-model embedding scripts may require their own Hugging Face access
tokens.

## 3. Download HistoTMEv2 checkpoints

The checkpoint repository `spatkar94/HistoTMEv2` is gated. First request access
in Hugging Face, then authenticate with a read token:

```bash
source .venv-histotme/bin/activate
huggingface-cli login
python scripts/download_histotme_checkpoints.py --local-dir models/HistoTMEv2
```

Pass `models/HistoTMEv2/checkpoints` as `--chkpts_dir` for inference.

## 4. Run inference

Bulk predictions for a directory of HDF5 embedding files:

```bash
mkdir -p outputs/histotme/bulk
cd external/HistoTME/HistoTME_regression
python predict_bulk.py \
  --h5_folder ../../../data/tcga_lung/embeddings \
  --chkpts_dir ../../../models/HistoTMEv2/checkpoints \
  --cohort TCGA_LUNG \
  --save_loc ../../../outputs/histotme/bulk \
  --embed virchow
```

Spatial predictions for one HDF5 embedding file:

```bash
mkdir -p outputs/histotme/spatial
cd external/HistoTME/HistoTME_regression
python predict_spatial.py \
  --h5_path ../../../data/tcga_lung/embeddings/example.h5 \
  --chkpts_dir ../../../models/HistoTMEv2/checkpoints \
  --save_loc ../../../outputs/histotme/spatial \
  --embed virchow
```

Use the `--embed` value that matches the foundation model used to create the
embeddings: `uni`, `uni2`, `virchow`, `virchow2`, `gigapath`, or `hoptimus0`.

## Notes

- HistoTME preprocessing can use NVIDIA cuCIM for faster WSI processing. cuCIM is
  optional; the upstream code falls back to OpenSlide for unsupported slides.
- Keep downloaded slides, embeddings, checkpoints, and predictions out of git.
  This repo ignores those paths by default.
