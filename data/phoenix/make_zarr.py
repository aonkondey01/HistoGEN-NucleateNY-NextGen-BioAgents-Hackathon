#!/usr/bin/env python3
"""Subset the PHOENIX TCGA AnnData to a patient cohort and write a chunked .zarr.

The PHOENIX atlas (atlas/tcga-atlas-nest-multi-cell-20x-discrete.h5ad) is a
~23 GB AnnData of ~14.99M cells x 377 NEST multi-cell embedding dims, with
per-cell spatial (x, y) in obsm['spatial'] and obs columns {slide, study}.
The ``slide`` column holds TCGA patient barcodes (e.g. TCGA-44-2661).

This selects the cells for a list of patients and writes them out as a
**chunked Zarr store** suitable for lazy / "live" loading in spatial image
viewers (Vitessce, napari-spatialdata, SpatialData, custom WebGL viewers).
The atlas is read in *backed* mode so only the selected rows are pulled into
memory.

Usage:
    pip install -r requirements.txt
    python make_zarr.py                         # default cohort -> demo/phoenix/cohort.zarr
    python make_zarr.py --patients TCGA-44-2661 TCGA-55-7815 ...
    python make_zarr.py --patients-file patients.txt --out my_cohort.zarr
    python make_zarr.py --zarr-format 2         # max viewer compatibility (default)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The 20-patient cohort from the request (TCGA-05-4410 is absent from PHOENIX).
DEFAULT_PATIENTS = [
    "TCGA-44-2661", "TCGA-55-7815", "TCGA-86-7701", "TCGA-86-8279", "TCGA-86-8672",
    "TCGA-05-4410", "TCGA-44-3917", "TCGA-55-7907", "TCGA-73-A9RS", "TCGA-86-7954",
    "TCGA-18-5595", "TCGA-37-3789", "TCGA-56-A5DR", "TCGA-70-6722", "TCGA-85-8277",
    "TCGA-18-3409", "TCGA-22-4613", "TCGA-56-5898", "TCGA-60-2698", "TCGA-L3-A524",
]

DEFAULT_H5AD = (
    Path(__file__).resolve().parent.parent
    / "demo"
    / "phoenix"
    / "tcga-atlas-nest-multi-cell-20x-discrete.h5ad"
)
LEGACY_H5AD = (
    Path(__file__).resolve().parent
    / "atlas"
    / "tcga-atlas-nest-multi-cell-20x-discrete.h5ad"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_path", type=Path, default=DEFAULT_H5AD)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "demo" / "phoenix" / "cohort.zarr")
    parser.add_argument("--patients", nargs="*", help="patient barcodes (default: built-in 20)")
    parser.add_argument("--patients-file", type=Path, help="file with one barcode per line")
    parser.add_argument("--row-chunk", type=int, default=4096, help="rows per chunk for X")
    parser.add_argument("--zarr-format", type=int, choices=[2, 3], default=2,
                        help="Zarr format version (2 = broadest viewer compatibility)")
    args = parser.parse_args()

    in_path = args.in_path
    if not in_path.exists() and in_path == DEFAULT_H5AD and LEGACY_H5AD.exists():
        in_path = LEGACY_H5AD
    if not in_path.exists():
        print(f"ERROR: input h5ad not found: {in_path}\n"
              f"  Fetch demo atlas: python scripts/demo/fetch_phoenix.py", file=sys.stderr)
        return 2

    if args.patients_file:
        patients = [ln.strip() for ln in args.patients_file.read_text().splitlines() if ln.strip()]
    else:
        patients = args.patients or DEFAULT_PATIENTS
    patients = list(dict.fromkeys(patients))  # de-dupe, keep order

    import anndata as ad
    import numpy as np
    import zarr

    print(f"Opening (backed) {in_path.name} ...")
    adata = ad.read_h5ad(in_path, backed="r")
    slide = adata.obs["slide"].astype(str)
    present = [p for p in patients if (slide == p).any()]
    missing = [p for p in patients if p not in present]
    if missing:
        print(f"  WARNING: {len(missing)} patient(s) not in atlas: {missing}")

    mask = slide.isin(present).to_numpy()
    print(f"  selecting {int(mask.sum()):,} cells from {len(present)} patients")

    # Pull only the selected rows into memory (subset is small).
    sub = adata[mask].to_memory()
    sub.obs["patient"] = sub.obs["slide"].astype(str)
    # Drop unused categorical levels so viewers show only this cohort.
    for col in ("slide", "study", "patient"):
        if col in sub.obs and hasattr(sub.obs[col], "cat"):
            sub.obs[col] = sub.obs[col].astype(str).astype("category")

    # Densify + rechunk X for lazy row-wise loading.
    X = np.asarray(sub.X, dtype="float32")
    sub.X = X

    out = args.out
    if out.exists():
        import shutil
        shutil.rmtree(out)

    n = X.shape[0]
    row_chunk = min(args.row_chunk, n)
    print(f"Writing {out.name} (zarr v{args.zarr_format}, X chunks=({row_chunk}, {X.shape[1]})) ...")
    sub.write_zarr(
        out,
        chunks=(row_chunk, X.shape[1]),
        **({"zarr_format": args.zarr_format} if _supports_zarr_format() else {}),
    )

    _summarize(out, sub)
    print(f"\nDONE -> {out}")
    print("Load lazily, e.g.:")
    print(f"  import anndata as ad; A = ad.read_zarr('{out}')")
    print(f"  # or stream with zarr: zarr.open('{out}', mode='r')")
    return 0


def _supports_zarr_format() -> bool:
    import inspect
    import anndata as ad
    try:
        return "zarr_format" in inspect.signature(ad.AnnData.write_zarr).parameters
    except (TypeError, ValueError):
        return False


def _summarize(out: Path, sub) -> None:
    import zarr
    g = zarr.open(str(out), mode="r")
    keys = list(g.keys()) if hasattr(g, "keys") else []
    print(f"  store keys: {keys}")
    print(f"  n_obs x n_vars: {sub.n_obs:,} x {sub.n_vars}")
    print(f"  obs columns: {list(sub.obs.columns)}")
    print(f"  obsm: {list(sub.obsm.keys())}")
    vc = sub.obs["patient"].value_counts()
    print(f"  patients: {len(vc)} (cells/patient min={int(vc.min())}, max={int(vc.max())})")


if __name__ == "__main__":
    raise SystemExit(main())
