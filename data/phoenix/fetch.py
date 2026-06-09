#!/usr/bin/env python3
"""Download PHOENIX model weights from Hugging Face for H&E → virtual RNA inference.

Model: https://huggingface.co/peng-lab/phoenix  (CC-BY-NC-4.0)

PHOENIX predicts spatially resolved gene expression from routine H&E whole-slide
images. Use ``inference.py`` (or ``scripts/demo/run_phoenix.py``) on your own slides.

The large TCGA AnnData file on the Hugging Face *dataset* repo is **demo-only**
(precomputed readouts for the bundled 20-patient cohort). Fetch it with
``fetch_demo_atlas.py`` — not required for inference on new H&E.

Prerequisites:
  Optional HF_TOKEN for faster downloads / rate limits.

Recommended NEST cell model (20× discrete):

    weights/flow/nest/multi/cell/20x/discrete/flow_model.pth   (~4.8 GB)
    statistics/nest/multi/cell/discrete/stats_table.npz

Usage:
    pip install -r requirements.txt
    python fetch.py
    python fetch.py --list
    python inference.py --svs slide.svs --out-dir ./outputs/my_slide
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

MODEL_REPO = "peng-lab/phoenix"
DEFAULT_FILES = [
    "weights/flow/nest/multi/cell/20x/discrete/flow_model.pth",
    "statistics/nest/multi/cell/discrete/stats_table.npz",
    "panels/xenium_human_multi.npy",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="path within the model repo (repeatable; defaults to NEST flow weights + stats)",
    )
    parser.add_argument("--list", action="store_true", help="list model repo files and exit")
    args = parser.parse_args()

    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN")

    if args.list:
        files = HfApi().list_repo_files(MODEL_REPO, repo_type="model", token=token)
        for path in files:
            print(path)
        return 0

    files = args.files or DEFAULT_FILES
    for rel in files:
        t0 = time.time()
        try:
            path = hf_hub_download(
                repo_id=MODEL_REPO,
                repo_type="model",
                filename=rel,
                local_dir=str(args.out_dir),
            )
        except Exception as err:
            print(f"FAIL {rel}: {err}", file=sys.stderr)
            return 1
        size_mb = os.path.getsize(path) / 1e6
        print(f"OK   {rel}  ({size_mb:.1f} MB, {(time.time() - t0) / 60:.1f} min) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
