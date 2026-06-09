#!/usr/bin/env python3
"""Download PHOENIX atlas AnnData into demo/phoenix/ for the HistoGEN demo."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from paths import PHOENIX_DIR  # noqa: E402

PHOENIX_FETCH = ROOT / "data" / "phoenix" / "fetch.py"
DEFAULT_FILE = "atlas/tcga-atlas-nest-multi-cell-20x-discrete.h5ad"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_FILE, help="path within peng-lab/phoenix dataset")
    parser.add_argument("--list", action="store_true", help="list remote files and exit")
    args = parser.parse_args()

    PHOENIX_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(PHOENIX_FETCH), "--out-dir", str(PHOENIX_DIR)]
    if args.list:
        cmd.append("--list")
    else:
        cmd.extend(["--file", args.file])
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
