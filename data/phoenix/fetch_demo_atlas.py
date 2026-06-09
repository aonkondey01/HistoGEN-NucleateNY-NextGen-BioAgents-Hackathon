#!/usr/bin/env python3
"""Download the TCGA demo AnnData (precomputed PHOENIX readouts) — demo cohort only.

Dataset: https://huggingface.co/datasets/peng-lab/phoenix

This ~23 GB file holds **reference cells already profiled on TCGA slides**. The
HistoGEN demo uses it to populate ``demo/data_package/`` without re-running GPU
inference. For your own H&E slides use ``fetch.py`` + ``inference.py`` instead.

Usage:
    python fetch_demo_atlas.py
    python fetch_demo_atlas.py --out-dir ../../demo/phoenix
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

DATASET_REPO = "peng-lab/phoenix"
DEFAULT_FILE = "atlas/tcga-atlas-nest-multi-cell-20x-discrete.h5ad"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", default=DEFAULT_FILE, help="path within the dataset repo")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "demo" / "phoenix",
    )
    parser.add_argument("--list", action="store_true", help="list dataset files and exit")
    args = parser.parse_args()

    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN")

    if args.list:
        files = HfApi().list_repo_files(DATASET_REPO, repo_type="dataset", token=token)
        for path in files:
            print(path)
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    path = hf_hub_download(
        repo_id=DATASET_REPO,
        repo_type="dataset",
        filename=args.file,
        local_dir=str(args.out_dir),
        token=token,
    )
    size_gb = os.path.getsize(path) / 1e9
    print(f"DONE  {path}  ({size_gb:.2f} GB, {(time.time() - t0) / 60:.1f} min)")
    print("Demo-only — for new H&E use: python fetch.py && python inference.py --svs ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
