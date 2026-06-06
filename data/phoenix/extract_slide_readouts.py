#!/usr/bin/env python3
"""Extract PHOENIX spatial readouts for a TCGA diagnostic slide.

PHOENIX ships TCGA pan-cancer data in the atlas AnnData file
(``atlas/tcga-atlas-nest-multi-cell-20x-discrete.h5ad``). The demo
``demo/demo.zarr`` SpatialData store uses the same 377-gene NEST readout
panel in ``tables/{table,spots_55um_table,spots_100um_table}``.

This script subsets atlas cells by slide ID and writes compact CSV/JSON
artifacts suitable for merging into the representative-patient bundles.

Usage:
    python fetch.py   # download atlas first (~23 GB)
    python extract_slide_readouts.py --case TCGA-56-5898
    python extract_slide_readouts.py --slide-id TCGA-56-5898-01Z-00-DX1
    python extract_slide_readouts.py --zarr demo/demo.zarr   # inspect demo schema
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

DATA_DIR = Path(__file__).resolve().parent
DEFAULT_ATLAS = DATA_DIR / "atlas" / "tcga-atlas-nest-multi-cell-20x-discrete.h5ad"
DEFAULT_DEMO_ZARR = DATA_DIR / "demo" / "demo.zarr"
SLIDES_META = DATA_DIR.parent / "tcga_lung" / "slides_metadata.tcga_lung.json"
REP_BUNDLE_ROOT = (
    DATA_DIR.parent / "tcga_lung" / "representative_patients" / "data_package" / "per_patient"
)
TILE_SIZE = 512
SIGNATURES = ["Treg", "Effector_cells", "Macrophages", "CAF"]


def _load_slide_record(case_or_slide: str) -> dict[str, Any]:
    slides = json.loads(SLIDES_META.read_text())
    key = case_or_slide.strip()
    for row in slides:
        if row.get("case_submitter_id") == key or key in row.get("file_name", ""):
            return row
    raise SystemExit(f"No diagnostic slide found for {case_or_slide!r} in {SLIDES_META}")


def _gene_names_from_demo_zarr(zarr_path: Path) -> list[str]:
    import zarr

    idx = zarr.open_array(str(zarr_path / "tables" / "table" / "var" / "_index"), mode="r")
    return [str(g) for g in idx[:]]


def _read_zarr_table(zarr_path: Path, table_name: str) -> dict[str, Any]:
    """Load one SpatialData AnnData table stored inside a PHOENIX zarr."""
    import zarr
    from scipy import sparse

    base = zarr_path / "tables" / table_name
    genes = [str(g) for g in zarr.open_array(str(base / "var" / "_index"), mode="r")[:]]
    spatial = np.asarray(zarr.open_array(str(base / "obsm" / "spatial"), mode="r")[:], dtype=float)
    xg = zarr.open_group(str(base / "X"), mode="r")
    data = np.asarray(xg["data"][:])
    indices = np.asarray(xg["indices"][:])
    indptr = np.asarray(xg["indptr"][:])
    x = sparse.csr_matrix((data, indices, indptr), shape=(spatial.shape[0], len(genes)))
    obs_index = [str(i) for i in zarr.open_array(str(base / "obs" / "_index"), mode="r")[:]]
    return {"table": table_name, "genes": genes, "spatial": spatial, "x": x, "obs_index": obs_index}


def extract_from_zarr(zarr_path: Path) -> dict[str, Any]:
    tables = {}
    for name in ("table", "spots_55um_table", "spots_100um_table"):
        if (zarr_path / "tables" / name).exists():
            tables[name] = _read_zarr_table(zarr_path, name)
    return {"source": str(zarr_path), "tables": tables}


def _subset_atlas(atlas_path: Path, slide_name: str, case_id: str | None = None):
    import anndata as ad

    adata = ad.read_h5ad(atlas_path, backed="r")
    slides = adata.obs["slide"].astype(str)
    candidates = [slide_name]
    if case_id:
        candidates.insert(0, case_id)
    if "-01Z" in slide_name:
        candidates.append(slide_name.split("-01Z")[0])
    mask = None
    matched = slide_name
    for cand in candidates:
        m = slides == cand
        if m.any():
            mask = m
            matched = cand
            break
    if mask is None:
        for cand in candidates:
            m = slides.str.contains(cand, regex=False)
            if m.any():
                mask = m
                matched = str(slides[m].iloc[0])
                break
    if mask is None or not mask.any():
        raise SystemExit(f"No cells in atlas for slide {slide_name!r}")
    sub = adata[mask].to_memory()
    adata.file.close()
    sub.uns["phoenix_slide_id"] = matched
    return sub


def _dense_matrix(adata) -> np.ndarray:
    x = adata.X
    if hasattr(x, "toarray"):
        return np.asarray(x.toarray(), dtype=np.float32)
    return np.asarray(x, dtype=np.float32)


def _spatial_xy(adata) -> np.ndarray:
    for key in ("spatial", "X_spatial", "spatial_coords"):
        if key in adata.obsm:
            return np.asarray(adata.obsm[key], dtype=float)
    raise SystemExit(f"No spatial coordinates in atlas obsm keys: {list(adata.obsm.keys())}")


def _write_cells_csv(path: Path, genes: list[str], spatial: np.ndarray, matrix: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["cell_id", "x", "y", *genes]
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for i in range(matrix.shape[0]):
            row = [i, float(spatial[i, 0]), float(spatial[i, 1]), *matrix[i].tolist()]
            w.writerow(row)


def _write_gene_summary(path: Path, genes: list[str], matrix: np.ndarray) -> None:
    means = matrix.mean(axis=0)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["gene", "mean_readout", "nonzero_fraction"])
        nz = (matrix > 0).mean(axis=0)
        for g, m, f in zip(genes, means, nz):
            w.writerow([g, float(m), float(f)])


def _tile_aggregates(spatial: np.ndarray, matrix: np.ndarray, genes: list[str], tile_size: int) -> list[dict]:
    xs, ys = spatial[:, 0], spatial[:, 1]
    x0, y0 = float(xs.min()), float(ys.min())
    tiles: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(zip(xs, ys)):
        tx = int(math.floor((x - x0) / tile_size))
        ty = int(math.floor((y - y0) / tile_size))
        tiles.setdefault((tx, ty), []).append(i)
    out: list[dict] = []
    for (tx, ty), idxs in sorted(tiles.items()):
        block = matrix[idxs].mean(axis=0)
        rec: dict[str, Any] = {
            "x": int(tx * tile_size + x0),
            "y": int(ty * tile_size + y0),
            "n_cells": len(idxs),
        }
        for g, v in zip(genes, block):
            rec[g] = float(v)
        out.append(rec)
    return out


def _signature_proxy_tiles(tiles: list[dict], genes: list[str]) -> list[dict]:
    """Map NEST gene readouts to coarse TME signature proxies for the UI."""
    gmap = {g: i for i, g in enumerate(genes)}

    def mean_genes(tile: dict, names: list[str]) -> float:
        vals = [tile.get(n, 0.0) for n in names if n in gmap]
        return float(np.mean(vals)) if vals else 0.0

    immune = ["CD3D", "CD3E", "CD8A", "CD8B", "GZMB", "PRF1", "IFNG"]
    treg = ["FOXP3", "IL2RA", "CTLA4", "IKZF2"]
    mac = ["CD68", "CD163", "CSF1R", "ADGRE1"]
    caf = ["ACTA2", "COL1A1", "COL1A2", "FAP", "PDGFRA", "DCN"]

    out = []
    for t in tiles:
        out.append(
            {
                "x": t["x"],
                "y": t["y"],
                "n_cells": t["n_cells"],
                "Treg": mean_genes(t, treg),
                "Effector_cells": mean_genes(t, immune),
                "Macrophages": mean_genes(t, mac),
                "CAF": mean_genes(t, caf),
            }
        )
    return out


def extract_from_atlas(
    atlas_path: Path, slide_name: str, genes: list[str], case_id: str | None = None
) -> dict[str, Any]:
    adata = _subset_atlas(atlas_path, slide_name, case_id=case_id)
    spatial = _spatial_xy(adata)
    matrix = _dense_matrix(adata)
    atlas_genes = [str(g) for g in adata.var_names]
    if genes and genes != atlas_genes:
        # Re-order to demo-zarr gene panel when names match.
        if set(atlas_genes) == set(genes):
            order = [atlas_genes.index(g) for g in genes]
            matrix = matrix[:, order]
        else:
            genes = atlas_genes
    else:
        genes = atlas_genes
    study = str(adata.obs["study"].iloc[0]) if "study" in adata.obs else ""
    phoenix_slide = adata.uns.get("phoenix_slide_id", slide_name)
    return {
        "source": str(atlas_path),
        "slide": slide_name,
        "phoenix_slide_id": phoenix_slide,
        "study": study,
        "n_cells": int(matrix.shape[0]),
        "n_genes": len(genes),
        "genes": genes,
        "spatial": spatial,
        "matrix": matrix,
    }


def write_outputs(
    bundle_dir: Path,
    case_id: str,
    slide_meta: dict[str, Any],
    extraction: dict[str, Any],
    *,
    copy_previews_from: Path | None = None,
) -> dict[str, Any]:
    genes = extraction["genes"]
    spatial = extraction["spatial"]
    matrix = extraction["matrix"]
    previews_dir = bundle_dir / "slide_previews"
    previews_dir.mkdir(parents=True, exist_ok=True)

    if copy_previews_from and copy_previews_from.exists():
        import shutil

        for png in copy_previews_from.glob("*.png"):
            if case_id in png.name:
                shutil.copy2(png, previews_dir / png.name)

    cells_csv = bundle_dir / "phoenix_cells.csv"
    summary_csv = bundle_dir / "phoenix_gene_summary.csv"
    tiles_json = bundle_dir / "phoenix_tiles.json"
    heatmap_json = bundle_dir / "phoenix_spatial_heatmap.json"

    _write_cells_csv(cells_csv, genes, spatial, matrix)
    _write_gene_summary(summary_csv, genes, matrix)
    tiles = _tile_aggregates(spatial, matrix, genes, TILE_SIZE)
    tiles_json.write_text(json.dumps({"slide": extraction["slide"], "tile_size": TILE_SIZE, "tiles": tiles}, indent=2))

    sig_tiles = _signature_proxy_tiles(tiles, genes)
    heatmap = {
        "case_id": case_id,
        "slide": extraction["slide"],
        "signature": "Treg",
        "tile_size": TILE_SIZE,
        "source": "phoenix_atlas",
        "tiles": sig_tiles,
    }
    heatmap_json.write_text(json.dumps(heatmap, indent=2))

    summary = {
        "case_submitter_id": case_id,
        "slide": extraction["slide"],
        "phoenix_slide_id": extraction.get("phoenix_slide_id", extraction["slide"]),
        "study": extraction.get("study", ""),
        "phoenix_source": extraction["source"],
        "n_cells": extraction["n_cells"],
        "n_genes": extraction["n_genes"],
        "spatial_extent": {
            "x_min": float(spatial[:, 0].min()),
            "x_max": float(spatial[:, 0].max()),
            "y_min": float(spatial[:, 1].min()),
            "y_max": float(spatial[:, 1].max()),
        },
        "outputs": {
            "cells": str(cells_csv.name),
            "gene_summary": str(summary_csv.name),
            "tiles": str(tiles_json.name),
            "spatial_heatmap": str(heatmap_json.name),
            "slide_previews": sorted(p.name for p in previews_dir.glob("*.png")),
        },
        "gdc_slide": slide_meta,
    }
    (bundle_dir / "phoenix_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case", help="TCGA case submitter id, e.g. TCGA-56-5898")
    p.add_argument("--slide-id", help="Full GDC slide filename substring")
    p.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    p.add_argument("--zarr", type=Path, help="Optional demo zarr path (schema / gene panel)")
    p.add_argument("--out-dir", type=Path, help="Output bundle directory")
    p.add_argument(
        "--previews-dir",
        type=Path,
        default=DATA_DIR.parent / "tcga_lung" / "previews",
        help="Directory with slide PNG previews to copy into bundle",
    )
    args = p.parse_args()

    if not args.case and not args.slide_id and not args.zarr:
        raise SystemExit("Provide --case, --slide-id, or --zarr")

    genes: list[str] = []
    zarr_path = args.zarr or (DEFAULT_DEMO_ZARR if DEFAULT_DEMO_ZARR.exists() else None)
    if zarr_path and zarr_path.exists():
        genes = _gene_names_from_demo_zarr(zarr_path)

    if args.zarr:
        zdata = extract_from_zarr(args.zarr)
        out = args.out_dir or (DATA_DIR / "extracted" / args.zarr.name)
        out.mkdir(parents=True, exist_ok=True)
        (out / "zarr_schema.json").write_text(
            json.dumps(
                {
                    "source": zdata["source"],
                    "tables": {
                        k: {
                            "n_obs": v["spatial"].shape[0],
                            "n_genes": len(v["genes"]),
                            "genes": v["genes"][:20],
                        }
                        for k, v in zdata["tables"].items()
                    },
                },
                indent=2,
            )
        )
        for tname, tbl in zdata["tables"].items():
            _write_cells_csv(out / f"{tname}_cells.csv", tbl["genes"], tbl["spatial"], tbl["x"].toarray())
            _write_gene_summary(out / f"{tname}_gene_summary.csv", tbl["genes"], tbl["x"].toarray())
        print(f"wrote zarr readouts to {out}")
        return 0

    slide_meta = _load_slide_record(args.case or args.slide_id)
    case_id = slide_meta["case_submitter_id"]
    slide_name = slide_meta["file_name"]
    if args.slide_id:
        slide_name = next(
            (s["file_name"] for s in json.loads(SLIDES_META.read_text()) if args.slide_id in s["file_name"]),
            slide_name,
        )

    if not args.atlas.exists():
        raise SystemExit(
            f"Atlas not found: {args.atlas}\nRun: cd {DATA_DIR} && python fetch.py"
        )

    extraction = extract_from_atlas(args.atlas, slide_name, genes, case_id=case_id)
    bundle_dir = args.out_dir or (REP_BUNDLE_ROOT / case_id)
    summary = write_outputs(
        bundle_dir,
        case_id,
        slide_meta,
        extraction,
        copy_previews_from=args.previews_dir,
    )

    # Update bundle_summary.json if present
    bundle_summary_path = bundle_dir / "bundle_summary.json"
    if bundle_summary_path.exists():
        bundle = json.loads(bundle_summary_path.read_text())
        bundle["phoenix_cells"] = summary["n_cells"]
        bundle["phoenix_genes"] = summary["n_genes"]
        bundle_summary_path.write_text(json.dumps(bundle, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
