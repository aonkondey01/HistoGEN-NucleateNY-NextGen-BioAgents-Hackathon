#!/usr/bin/env python3
"""Render static spatial PNG maps for PHOENIX gene readouts.

Reads ``phoenix_cells.csv`` from a representative-patient bundle (or any
CSV with columns ``x``, ``y``, and gene symbols) and writes one PNG per gene.

Usage:
    python plot_gene_maps.py --case TCGA-56-5898 --genes CD3D PDCD1 CD68
    python plot_gene_maps.py --cells path/to/phoenix_cells.csv --genes CD3D
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from PIL import Image

DATA_DIR = Path(__file__).resolve().parent
REP_BUNDLE_ROOT = (
    DATA_DIR.parent / "tcga_lung" / "representative_patients" / "data_package" / "per_patient"
)

GENE_LABELS = {"PDCD1": "PD-1"}


def _load_cells(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], list[str]]:
    with path.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    if not rows:
        raise SystemExit(f"No rows in {path}")
    genes = [c for c in rows[0].keys() if c not in ("cell_id", "x", "y")]
    x = np.array([float(r["x"]) for r in rows], dtype=float)
    y = np.array([float(r["y"]) for r in rows], dtype=float)
    values = {g: np.array([float(r[g]) for r in rows], dtype=float) for g in genes}
    return x, y, values, genes


def _thumbnail_path(bundle_dir: Path, case_id: str) -> Path | None:
    previews = bundle_dir / "slide_previews"
    if not previews.exists():
        return None
    matches = sorted(previews.glob(f"{case_id}*.thumbnail.png"))
    return matches[0] if matches else None


def plot_gene_map(
    x: np.ndarray,
    y: np.ndarray,
    values: np.ndarray,
    gene: str,
    out: Path,
    *,
    background: Path | None = None,
    point_size: float = 18.0,
    dpi: int = 150,
) -> Path:
    label = GENE_LABELS.get(gene, gene)
    xmin, xmax = float(x.min()), float(x.max())
    ymin, ymax = float(y.min()), float(y.max())

    fig_w = 10
    fig_h = 10 * (ymax - ymin) / max(xmax - xmin, 1.0)
    fig, ax = plt.subplots(figsize=(fig_w, max(fig_h, 6)), dpi=dpi)

    if background and background.exists():
        img = np.asarray(Image.open(background).convert("RGB"))
        ax.imshow(img, extent=(xmin, xmax, ymax, ymin), origin="upper", aspect="auto", zorder=0)

    vmax = float(np.percentile(values, 99)) if values.size else 1.0
    vmax = max(vmax, 1e-6)
    norm = colors.PowerNorm(gamma=0.6, vmin=0.0, vmax=vmax)
    sc = ax.scatter(
        x,
        y,
        c=values,
        s=point_size,
        cmap="inferno",
        norm=norm,
        linewidths=0,
        alpha=0.92,
        zorder=2,
    )
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymax, ymin)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"{label}  (PHOENIX NEST readout)", fontsize=14, pad=10)
    cbar = fig.colorbar(sc, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("inferred expression", rotation=270, labelpad=14)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case", help="TCGA case id, e.g. TCGA-56-5898")
    p.add_argument("--cells", type=Path, help="phoenix_cells.csv path")
    p.add_argument("--out-dir", type=Path, help="output directory for PNGs")
    p.add_argument("--genes", nargs="+", required=True, help="gene symbols to plot")
    p.add_argument("--no-background", action="store_true", help="skip H&E thumbnail underlay")
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
        raise SystemExit(f"Cells file not found: {cells_path}")

    x, y, gene_values, available = _load_cells(cells_path)
    out_dir = args.out_dir or (bundle_dir / "phoenix_gene_maps")
    background = None if args.no_background else _thumbnail_path(bundle_dir, case_id)

    written: list[Path] = []
    for gene in args.genes:
        key = gene
        if key not in gene_values and gene == "PD-1" and "PDCD1" in gene_values:
            key = "PDCD1"
        if key not in gene_values:
            raise SystemExit(f"Gene {gene!r} not in {cells_path} (available example: {available[:8]}...)")
        fname = f"{case_id}.{GENE_LABELS.get(key, key)}.png".replace("/", "-")
        out = plot_gene_map(x, y, gene_values[key], key, out_dir / fname, background=background)
        written.append(out)
        print(f"wrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
