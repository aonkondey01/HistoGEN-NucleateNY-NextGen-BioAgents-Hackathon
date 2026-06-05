#!/usr/bin/env python3
"""Download gated HistoTMEv2 checkpoints from Hugging Face."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-id",
        default="spatkar94/HistoTMEv2",
        help="Hugging Face model repository to download.",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=Path("models/HistoTMEv2"),
        help="Directory where the repository snapshot should be stored.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("HF_TOKEN"),
        help="Hugging Face token. Defaults to HF_TOKEN or cached login.",
    )
    args = parser.parse_args()

    args.local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=args.repo_id,
        local_dir=args.local_dir,
        token=args.token,
    )
    print(f"Downloaded {args.repo_id} to {args.local_dir}")
    print(f"Use --chkpts_dir {args.local_dir / 'checkpoints'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
