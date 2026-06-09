#!/usr/bin/env python3
"""Register PHOENIX atlas cell coordinates onto a TCGA H&E thumbnail.

Combines the global PHOENIX affine (axis swap + 20×→40×) with optional
contour ICP and Farneback optical-flow warping, following the KPAR20FC
registration workflow.

Usage:
    python register_phoenix_to_he.py --case TCGA-56-5898
    python register_phoenix_to_he.py --cells path/to/phoenix_cells.csv --svs slide.svs
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image

from coordinate_map import slide_dimensions
from registration import save_registration_artifacts, register_phoenix_cells

DATA_DIR = Path(__file__).resolve().parent
REP_BUNDLE_ROOT = (
    DATA_DIR.parent / "demo" / "data_package" / "per_patient"
)


def _load_cells(path: Path) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    genes = [c for c in rows[0].keys() if c not in ("cell_id", "x", "y")]
    coords = np.array([[float(r["x"]), float(r["y"])] for r in rows], dtype=float)
    values = {g: np.array([float(r[g]) for r in rows], dtype=float) for g in genes}
    return coords, values


def _write_registered_csv(
    out_path: Path,
    cell_ids: list[str] | None,
    result,
    gene_values: dict[str, np.ndarray],
    genes: list[str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "cell_id",
        "phoenix_x",
        "phoenix_y",
        "thumb_x_affine",
        "thumb_y_affine",
        "thumb_x",
        "thumb_y",
        "slide_x_l0",
        "slide_y_l0",
        *genes,
    ]
    with out_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for i in range(len(result.coords_phoenix)):
            row = [
                cell_ids[i] if cell_ids else i,
                result.coords_phoenix[i, 0],
                result.coords_phoenix[i, 1],
                result.coords_thumb_affine[i, 0],
                result.coords_thumb_affine[i, 1],
                result.coords_thumb_warped[i, 0],
                result.coords_thumb_warped[i, 1],
                result.coords_slide_l0[i, 0],
                result.coords_slide_l0[i, 1],
                *[gene_values[g][i] for g in genes],
            ]
            w.writerow(row)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case", help="TCGA case id")
    p.add_argument("--cells", type=Path, help="phoenix_cells.csv")
    p.add_argument("--svs", type=Path, help="diagnostic .svs")
    p.add_argument("--out-dir", type=Path)
    p.add_argument("--no-icp", action="store_true")
    p.add_argument("--no-flow", action="store_true")
    args = p.parse_args()

    if args.cells:
        cells_path = args.cells
        case_id = args.case or cells_path.parent.name
        bundle_dir = cells_path.parent
    elif args.case:
        case_id = args.case
        bundle_dir = REP_BUNDLE_ROOT / case_id
        cells_path = bundle_dir / "phoenix_cells.csv"
    else:
        raise SystemExit("Provide --case or --cells")

    if not cells_path.exists():
        raise SystemExit(f"Missing {cells_path}")

    thumb_path = bundle_dir / "slide_previews" / f"{case_id}.thumbnail.png"
    matches = sorted((bundle_dir / "slide_previews").glob(f"{case_id}*.thumbnail.png"))
    if matches:
        thumb_path = matches[0]
    if not thumb_path.exists():
        raise SystemExit(f"Missing thumbnail {thumb_path}")

    svs = args.svs
    if svs is None:
        import sys

        demo_paths = DATA_DIR.parent / "demo"
        if str(demo_paths) not in sys.path:
            sys.path.insert(0, str(demo_paths))
        from paths import find_wsi

        svs = find_wsi(case_id)
    if svs is None or not svs.exists():
        raise SystemExit("Need --svs or downloaded WSI under demo/WSI/ or data/tcga_lung/WSI/")

    coords_phx, gene_values = _load_cells(cells_path)
    he_thumb = np.asarray(Image.open(thumb_path).convert("RGB"))
    slide_wh = slide_dimensions(svs)

    result = register_phoenix_cells(
        coords_phx,
        he_thumb,
        slide_wh,
        case_id=case_id,
        use_contour_icp=not args.no_icp,
        use_optical_flow=not args.no_flow,
    )

    out_dir = args.out_dir or (bundle_dir / "phoenix_registration")
    save_registration_artifacts(result, he_thumb, out_dir, gene_values=gene_values)

    genes = [g for g in gene_values]
    reg_csv = out_dir / "phoenix_cells_registered.csv"
    _write_registered_csv(reg_csv, None, result, gene_values, genes)

    # Update bundle summary
    summary_path = bundle_dir / "phoenix_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
    else:
        summary = {"case_submitter_id": case_id}
    summary["registration"] = {
        "directory": str(out_dir.relative_to(bundle_dir.parent.parent.parent)) if out_dir.is_relative_to(bundle_dir.parent.parent.parent) else str(out_dir),
        "registered_cells_csv": reg_csv.name,
        "metrics": result.metrics,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(result.as_dict(), indent=2))
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
