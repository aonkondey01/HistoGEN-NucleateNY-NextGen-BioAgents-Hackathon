# PHOENIX spatial transcriptomics

## Demo fetch (preferred)

```bash
python scripts/demo/fetch_phoenix.py
# → demo/phoenix/tcga-atlas-nest-multi-cell-20x-discrete.h5ad (~23 GB)
```

## General fetch

```bash
cd data/phoenix
pip install -r requirements.txt
python fetch.py --list
python fetch.py   # → data/phoenix/atlas/ (legacy location)
```

## Per-slide readouts (demo patients)

```bash
cd data/phoenix
python extract_slide_readouts.py --case TCGA-56-5898
python register_phoenix_to_he.py --case TCGA-56-5898 --svs ../../demo/WSI/....svs
```

Bundles land in `demo/data_package/per_patient/{case_id}/`.

## Optional Zarr subset

`make_zarr.py` writes to `demo/phoenix/cohort.zarr` (not committed). Do **not**
recreate `data/phoenix/cohort.zarr` — that path was removed.

## License

PHOENIX is **CC-BY-NC-ND-4.0** — non-commercial, no derivatives.
