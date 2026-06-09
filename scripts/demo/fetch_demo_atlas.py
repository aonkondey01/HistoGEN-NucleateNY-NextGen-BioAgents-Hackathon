#!/usr/bin/env python3
"""Download TCGA demo AnnData into demo/phoenix/ (precomputed readouts — demo only)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from paths import PHOENIX_DIR  # noqa: E402

FETCH = ROOT / "data" / "phoenix" / "fetch_demo_atlas.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    PHOENIX_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(FETCH), "--out-dir", str(PHOENIX_DIR)]
    if args.list:
        cmd.append("--list")
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
