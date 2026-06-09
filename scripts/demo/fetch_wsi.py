#!/usr/bin/env python3
"""Download diagnostic WSIs for the 20-patient HistoGEN demo cohort."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from paths import MANIFEST, PATIENTS_JSON, SLIDES_META, WSI_DIR  # noqa: E402

TCGA_LUNG = ROOT / "data" / "tcga_lung"


def _case_ids(limit: int | None) -> list[str]:
    rep = json.loads(PATIENTS_JSON.read_text())
    ids = [p["case_submitter_id"] for p in rep["patients"]]
    return ids[:limit] if limit else ids


def _write_manifest_subset(case_ids: list[str], out: Path) -> None:
    slides = {s["case_submitter_id"]: s for s in json.loads(SLIDES_META.read_text())}
    lines = ["id\tfilename\tmd5\tsize\tstate\n"]
    for cid in case_ids:
        row = slides[cid]
        lines.append(
            f"{row['file_id']}\t{row['file_name']}\t{row['md5sum']}\t{row['file_size']}\treleased\n"
        )
    out.write_text("".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="download first N demo patients only")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    case_ids = _case_ids(args.limit)
    WSI_DIR.mkdir(parents=True, exist_ok=True)
    manifest = ROOT / "demo" / ".wsi.manifest.txt"
    _write_manifest_subset(case_ids, manifest)

    cmd = [
        sys.executable,
        str(TCGA_LUNG / "download.py"),
        "--manifest",
        str(manifest),
        "--out-dir",
        str(WSI_DIR),
        "--backend",
        "http",
        "--workers",
        str(args.workers),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    print(f"Downloading {len(case_ids)} demo WSIs -> {WSI_DIR}")
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
    finally:
        manifest.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
