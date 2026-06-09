#!/usr/bin/env python3
"""Build demo UI assets: slide previews, PHOENIX spatial JSON, embedding data."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from paths import (  # noqa: E402
    BUNDLE_ROOT,
    DEMO_ROOT,
    MANIFEST,
    PATIENTS_JSON,
    SLIDES_META,
    WSI_DIR,
    atlas_path,
    find_wsi,
)

TCGA_LUNG = ROOT / "data" / "tcga_lung"
PHOENIX = ROOT / "data" / "phoenix"

SIGNATURES = ["Treg", "Effector_cells", "Macrophages", "CAF"]
IMMUNE = ["CD3D", "CD3E", "CD8A", "CD8B", "GZMB", "PRF1", "IFNG"]
TREG = ["FOXP3", "IL2RA", "CTLA4", "IKZF2"]
MAC = ["CD68", "CD163", "CSF1R", "ADGRE1"]
CAF_GENES = ["ACTA2", "COL1A1", "COL1A2", "FAP", "PDGFRA", "DCN"]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def _patient_ids(rep: dict) -> list[str]:
    return [p["case_submitter_id"] for p in rep["patients"]]


def _write_manifest_subset(case_ids: list[str], out: Path) -> Path:
    slides = {s["case_submitter_id"]: s for s in json.loads(SLIDES_META.read_text())}
    lines = ["id\tfilename\tmd5\tsize\tstate\n"]
    for cid in case_ids:
        s = slides[cid]
        lines.append(f"{s['file_id']}\t{s['file_name']}\t{s['md5sum']}\t{s['file_size']}\treleased\n")
    out.write_text("".join(lines))
    return out


def _mean_genes(row: dict, genes: list[str]) -> float:
    vals = [float(row[g]) for g in genes if g in row]
    return float(np.mean(vals)) if vals else 0.0


def _export_ui_spatial_from_registered(reg_csv: Path, case_id: str, out_json: Path, tile_size: int = 128) -> None:
    with reg_csv.open() as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return
    xs = np.array([float(r["thumb_x"]) for r in rows])
    ys = np.array([float(r["thumb_y"]) for r in rows])
    x0, y0 = float(xs.min()), float(ys.min())
    buckets: dict[tuple[int, int], list[dict]] = {}
    for r in rows:
        x, y = float(r["thumb_x"]), float(r["thumb_y"])
        tx = int(math.floor((x - x0) / tile_size))
        ty = int(math.floor((y - y0) / tile_size))
        buckets.setdefault((tx, ty), []).append(r)
    tiles = []
    for (tx, ty), group in sorted(buckets.items()):
        tiles.append(
            {
                "x": int(tx * tile_size + x0),
                "y": int(ty * tile_size + y0),
                "n_cells": len(group),
                "Treg": float(np.mean([_mean_genes(r, TREG) for r in group])),
                "Effector_cells": float(np.mean([_mean_genes(r, IMMUNE) for r in group])),
                "Macrophages": float(np.mean([_mean_genes(r, MAC) for r in group])),
                "CAF": float(np.mean([_mean_genes(r, CAF_GENES) for r in group])),
            }
        )
    payload = {
        "case_id": case_id,
        "signature": "Treg",
        "tile_size": tile_size,
        "source": "phoenix_registered",
        "tiles": tiles,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2))


def _export_ui_spatial_from_phoenix(bundle_dir: Path, case_id: str, out_json: Path) -> bool:
    src = bundle_dir / "phoenix_spatial_heatmap.json"
    if not src.exists():
        return False
    data = json.loads(src.read_text())
    data["case_id"] = case_id
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, indent=2))
    return True


def process_patient(case_id: str, *, skip_registration: bool) -> dict:
    bundle = BUNDLE_ROOT / case_id
    bundle.mkdir(parents=True, exist_ok=True)
    status: dict = {"case_id": case_id, "steps": []}

    atlas = atlas_path()
    if not (bundle / "phoenix_cells.csv").exists() and atlas.is_file():
        _run([sys.executable, str(PHOENIX / "extract_slide_readouts.py"), "--case", case_id])
        status["steps"].append("phoenix_extract")

    svs = find_wsi(case_id)
    if svs is None:
        status["steps"].append("missing_wsi")
        return status

    previews = bundle / "slide_previews"
    thumb = previews / f"{case_id}.thumbnail.png"
    if not thumb.exists():
        previews.mkdir(parents=True, exist_ok=True)
        _run(
            [
                sys.executable,
                str(TCGA_LUNG / "slide.py"),
                "thumbnail",
                str(svs),
                "--out",
                str(thumb),
                "--max-dim",
                "1536",
            ]
        )
        crop = previews / f"{case_id}.tissue_crop.png"
        _run([sys.executable, str(TCGA_LUNG / "slide.py"), "crop", str(svs), "--out", str(crop)])
        status["steps"].append("slide_png")

    reg_csv = bundle / "phoenix_registration" / "phoenix_cells_registered.csv"
    if reg_csv.exists():
        status["steps"].append("registration_present")
    elif not skip_registration:
        svs = find_wsi(case_id)
        if svs is not None and (bundle / "phoenix_cells.csv").exists():
            _run(
                [
                    sys.executable,
                    str(PHOENIX / "register_phoenix_to_he.py"),
                    "--case",
                    case_id,
                    "--svs",
                    str(svs),
                ]
            )
            status["steps"].append("registration")
        else:
            status["steps"].append("registration_skipped")

    return status


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", nargs="*")
    p.add_argument("--limit", type=int)
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--download-only", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--skip-registration", action="store_true")
    args = p.parse_args()

    rep = json.loads(PATIENTS_JSON.read_text())
    case_ids = args.cases or _patient_ids(rep)
    if args.limit:
        case_ids = case_ids[: args.limit]

    missing = [c for c in case_ids if find_wsi(c) is None]
    if missing and not args.skip_download:
        manifest = _write_manifest_subset(missing, ROOT / "demo" / ".wsi.manifest.txt")
        _run(
            [
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
        )
        manifest.unlink(missing_ok=True)
        if args.download_only:
            return 0

    results = []
    for cid in case_ids:
        print(f"\n=== {cid} ===", flush=True)
        try:
            results.append(process_patient(cid, skip_registration=args.skip_registration))
        except subprocess.CalledProcessError as err:
            results.append({"case_id": cid, "error": str(err)})

    summary_path = DEMO_ROOT / "representative_assets_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))

    print(f"\nWrote asset summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
