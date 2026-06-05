#!/usr/bin/env python3
"""Download the GigaTIME model weights from Hugging Face.

Repo: https://huggingface.co/prov-gigatime/GigaTIME  (GATED + custom license)

This repo is **gated** ("Agree and access repository" required) and licensed
under the custom PROV-GIGATIME terms: **non-commercial research use only, and
the model may NOT be redistributed**. Do not commit the weights to git.

Prerequisites:
  1. Accept the gate at the URL above while logged into your HF account.
  2. Provide a token from that account via the HF_TOKEN env var. On a Cloud
     Agent, add it under Dashboard -> Cloud Agents -> Secrets as HF_TOKEN.

Files in the repo: model.pth (~36.7 MB), config.json, README.md, LICENSE.

Usage:
    pip install -r requirements.txt
    export HF_TOKEN=...           # token for an account that accepted the gate
    python fetch.py              # downloads model.pth + config.json here
    python fetch.py --all        # also grab README.md + LICENSE
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ID = "prov-gigatime/GigaTIME"
CORE_FILES = ["model.pth", "config.json"]
EXTRA_FILES = ["README.md", "LICENSE"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--all", action="store_true", help="also fetch README.md + LICENSE")
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        print(
            "ERROR: HF_TOKEN is not set. This repo is gated.\n"
            "  1) Accept the gate at https://huggingface.co/prov-gigatime/GigaTIME\n"
            "  2) export HF_TOKEN=<token for that account>  (or add it as a\n"
            "     Cloud Agent secret in Dashboard -> Cloud Agents -> Secrets)",
            file=sys.stderr,
        )
        return 2

    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import GatedRepoError, HfHubHTTPError

    files = CORE_FILES + (EXTRA_FILES if args.all else [])
    for fname in files:
        try:
            path = hf_hub_download(
                repo_id=REPO_ID,
                filename=fname,
                local_dir=str(args.out_dir),
                token=token,
            )
            size_mb = os.path.getsize(path) / 1e6
            print(f"OK   {fname:14s} {size_mb:8.1f} MB -> {path}")
        except GatedRepoError:
            print(
                f"FAIL {fname}: access denied. Make sure your HF account accepted "
                f"the gate at https://huggingface.co/{REPO_ID}",
                file=sys.stderr,
            )
            return 1
        except HfHubHTTPError as err:
            print(f"FAIL {fname}: {err}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
