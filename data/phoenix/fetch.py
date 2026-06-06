#!/usr/bin/env python3
"""Download files from the PHOENIX TCGA atlas on Hugging Face.

Dataset: https://huggingface.co/datasets/peng-lab/phoenix  (public,
license CC-BY-NC-ND-4.0). Uses Xet-accelerated transfer via huggingface_hub.

The flagship file is the pan-cancer cell atlas:
    atlas/tcga-atlas-nest-multi-cell-20x-discrete.h5ad   (~23.4 GB)
an AnnData of ~14.99M cells x 377 NEST multi-cell embedding dims, with
spatial (x, y) per cell and obs columns {slide, study} spanning 32 TCGA
projects / 9,544 slides (incl. TCGA-LUAD + TCGA-LUSC).

HF_TOKEN is optional for this public dataset (set it only to raise rate
limits or to access gated files). On a Cloud Agent, add it under
Dashboard -> Cloud Agents -> Secrets as HF_TOKEN.

Usage:
    pip install -r requirements.txt
    python fetch.py                       # grab the default atlas file
    python fetch.py --file atlas/<other>.h5ad
    python fetch.py --list                # list files in the dataset
    python extract_slide_readouts.py --case TCGA-56-5898   # subset atlas cells
    python register_phoenix_to_he.py --case TCGA-56-5898 # affine + optical-flow warp
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

REPO_ID = "peng-lab/phoenix"
DEFAULT_FILE = "atlas/tcga-atlas-nest-multi-cell-20x-discrete.h5ad"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", default=DEFAULT_FILE, help="path within the dataset repo")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--list", action="store_true", help="list dataset files and exit")
    args = parser.parse_args()

    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN")  # optional; dataset is public

    if args.list:
        files = HfApi().list_repo_files(REPO_ID, repo_type="dataset", token=token)
        for f in files:
            print(f)
        return 0

    t0 = time.time()
    path = hf_hub_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        filename=args.file,
        local_dir=str(args.out_dir),
        token=token,
    )
    size_gb = os.path.getsize(path) / 1e9
    print(f"DONE  {path}  ({size_gb:.2f} GB, {(time.time() - t0) / 60:.1f} min)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
