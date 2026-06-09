#!/usr/bin/env python3
"""Deprecated — use scripts/demo/build_ui_assets.py instead."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

NEW = Path(__file__).resolve().parent / "demo" / "build_ui_assets.py"

if __name__ == "__main__":
    print("Note: build_representative_ui_assets.py moved to scripts/demo/build_ui_assets.py")
    raise SystemExit(subprocess.call([sys.executable, str(NEW), *sys.argv[1:]]))
