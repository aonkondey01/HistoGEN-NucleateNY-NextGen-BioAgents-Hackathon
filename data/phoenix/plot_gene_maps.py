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

from coordinate_map import DEFAULT_TCGA_MAP, PhoenixCoordinateMap, slide_dimensions

DATA_DIR = Path(__file__).resolve().parent
REP_BUNDLE_ROOT = (
    DATA_DIR.parent / "tcga_lung" / "representative_patients" / "data_package" / "per_patient"
)

GENE_LABELS = {"PDCD1": "PD-1"}


def _registered_cells_path(bundle_dir: Path) -> Path | None:
    reg = bundle_dir / "phoenix_registration" / "phoenix_cells_registered.csv"
    return reg if reg.exists() else None


def _load_cells(path: Path, bundle_dir: Path | None = None) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], list[str], str]:
    reg = _registered_cells_path(bundle_dir) if bundle_dir else None
    src = reg or path
    with src.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    if not rows:
        raise SystemExit(f"No rows in {src}")
    skip = {
        "cell_id",
        "x",
        "y",
        "phoenix_x",
        "phoenix_y",
        "thumb_x_affine",
        "thumb_y_affine",
        "thumb_x",
        "thumb_y",
        "slide_x_l0",
        "slide_y_l0",
    }
    genes = [c for c in rows[0].keys() if c not in skip]
    if reg:
        x = np.array([float(r["thumb_x"]) for r in rows], dtype=float)
        y = np.array([float(r["thumb_y"]) for r in rows], dtype=float)
        coord_src = "registered"
    else:
        x = np.array([float(r["x"]) for r in rows], dtype=float)
        y = np.array([float(r["y"]) for r in rows], dtype=float)
        coord_src = "phoenix"
    values = {g: np.array([float(r[g]) for r in rows], dtype=float) for g in genes}
    return x, y, values, genes, coord_src


def _thumbnail_path(bundle_dir: Path, case_id: str) -> Path | None:
    previews = bundle_dir / "slide_previews"
    if not previews.exists():
        return None
    matches = sorted(previews.glob(f"{case_id}*.thumbnail.png"))
    return matches[0] if matches else None


def _transform_phoenix_to_thumb(
    x_phx: np.ndarray,
    y_phx: np.ndarray,
    slide_wh: tuple[int, int],
    thumb_wh: tuple[int, int],
    coord_map: PhoenixCoordinateMap,
) -> tuple[np.ndarray, np.ndarray]:
    tx = np.empty_like(x_phx)
    ty = np.empty_like(y_phx)
    for i, (xp, yp) in enumerate(zip(x_phx, y_phx)):
        tx[i], ty[i] = coord_map.phoenix_to_thumbnail(xp, yp, slide_wh, thumb_wh)
    return tx, ty


def plot_gene_map(
    x_plot: np.ndarray,
    y_plot: np.ndarray,
    values: np.ndarray,
    gene: str,
    out: Path,
    *,
    background: Path | None = None,
    coord_space: str = "phoenix",
    slide_wh: tuple[int, int] | None = None,
    coord_map: PhoenixCoordinateMap = DEFAULT_TCGA_MAP,
    point_size: float = 18.0,
    dpi: int = 150,
) -> Path:
    label = GENE_LABELS.get(gene, gene)

    if background and background.exists():
        thumb = Image.open(background).convert("RGB")
        thumb_w, thumb_h = thumb.size
        img = np.asarray(thumb)
        if coord_space == "registered":
            plot_x, plot_y = x_plot, y_plot
        else:
            if slide_wh is None:
                raise SystemExit("slide_wh is required when plotting on a thumbnail background")
            plot_x, plot_y = _transform_phoenix_to_thumb(x_plot, y_plot, slide_wh, (thumb_w, thumb_h), coord_map)
        fig_w = 10
        fig_h = 10 * thumb_h / max(thumb_w, 1)
        fig, ax = plt.subplots(figsize=(fig_w, max(fig_h, 6)), dpi=dpi)
        ax.imshow(img, extent=(0, thumb_w, thumb_h, 0), origin="upper", aspect="equal", zorder=0)
        xmin, xmax = 0, thumb_w
        ymin, ymax = 0, thumb_h
    else:
        fig, ax = plt.subplots(figsize=(10, 8), dpi=dpi)
        plot_x, plot_y = x_plot, y_plot
        xmin, xmax = float(x_plot.min()), float(x_plot.max())
        ymin, ymax = float(y_plot.min()), float(y_plot.max())

    vmax = float(np.percentile(values, 99)) if values.size else 1.0
    vmax = max(vmax, 1e-6)
    norm = colors.PowerNorm(gamma=0.6, vmin=0.0, vmax=vmax)
    sc = ax.scatter(
        plot_x,
        plot_y,
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
    p.add_argument("--svs", type=Path, help="diagnostic .svs for slide dimensions (auto-detect if omitted)")
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

    x, y, gene_values, available, coord_src = _load_cells(cells_path, bundle_dir)
    out_dir = args.out_dir or (bundle_dir / "phoenix_gene_maps")
    background = None if args.no_background else _thumbnail_path(bundle_dir, case_id)

    slide_wh: tuple[int, int] | None = None
    if background and coord_src != "registered":
        svs = args.svs
        if svs is None:
            wsi_root = DATA_DIR.parent / "tcga_lung" / "WSI"
            matches = sorted(wsi_root.rglob(f"*{case_id}*.svs"))
            svs = matches[0] if matches else None
        if svs is None or not svs.exists():
            raise SystemExit(f"Need --svs or downloaded WSI for {case_id} to map coordinates")
        slide_wh = slide_dimensions(svs)

    written: list[Path] = []
    for gene in args.genes:
        key = gene
        if key not in gene_values and gene == "PD-1" and "PDCD1" in gene_values:
            key = "PDCD1"
        if key not in gene_values:
            raise SystemExit(f"Gene {gene!r} not in {cells_path} (available example: {available[:8]}...)")
        fname = f"{case_id}.{GENE_LABELS.get(key, key)}.png".replace("/", "-")
        out = plot_gene_map(
            x,
            y,
            gene_values[key],
            key,
            out_dir / fname,
            background=background,
            coord_space=coord_src,
            slide_wh=slide_wh,
        )
        written.append(out)
        print(f"wrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
