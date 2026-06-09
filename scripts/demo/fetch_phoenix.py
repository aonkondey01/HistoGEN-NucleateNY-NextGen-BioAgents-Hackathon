#!/usr/bin/env python3
"""Download PHOENIX inference weights into data/phoenix/."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHOENIX = ROOT / "data" / "phoenix"
FETCH = PHOENIX / "fetch.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list remote model files")
    parser.add_argument("--file", action="append", dest="files", help="specific weight file(s) to fetch")
    args = parser.parse_args()

    cmd = [sys.executable, str(FETCH), "--out-dir", str(PHOENIX)]
    if args.list:
        cmd.append("--list")
    elif args.files:
        for f in args.files:
            cmd.extend(["--file", f])
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
