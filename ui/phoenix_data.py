"""Load PHOENIX per-patient spatial readout bundles for the RNA viewer."""

from __future__ import annotations

import csv
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = REPO_ROOT / "data/tcga_lung/representative_patients/data_package/per_patient"
PHOENIX_DIR = REPO_ROOT / "data/phoenix"

COORD_SKIP = {
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


def bundle_dir(case_id: str) -> Path:
    return BUNDLE_ROOT / case_id


def has_phoenix_bundle(case_id: str) -> bool:
    return (bundle_dir(case_id) / "phoenix_summary.json").is_file()


@lru_cache(maxsize=8)
def load_summary(case_id: str) -> dict[str, Any]:
    path = bundle_dir(case_id) / "phoenix_summary.json"
    if not path.is_file():
        raise FileNotFoundError(f"No PHOENIX bundle for {case_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def load_gene_summary(case_id: str) -> list[dict[str, Any]]:
    path = bundle_dir(case_id) / "phoenix_gene_summary.csv"
    if not path.is_file():
        raise FileNotFoundError(f"No gene summary for {case_id!r}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "gene": row["gene"],
                "mean": float(row["mean"]),
                "nonzeroFraction": float(row["nonzero_fraction"]),
                "max": float(row["max"]),
            })
    rows.sort(key=lambda item: item["mean"], reverse=True)
    return rows


def _preview_path(case_id: str, kind: str) -> Path | None:
    previews = bundle_dir(case_id) / "slide_previews"
    if not previews.is_dir():
        return None
    matches = sorted(previews.glob(f"{case_id}*.{kind}.png"))
    return matches[0] if matches else None


@lru_cache(maxsize=8)
def thumbnail_size(case_id: str) -> tuple[int, int]:
    for kind in ("thumbnail", "tissue_crop"):
        path = _preview_path(case_id, kind)
        if path and path.is_file():
            from PIL import Image

            with Image.open(path) as image:
                return image.size
    return (1536, 1334)


def _registered_cells_path(case_id: str) -> Path | None:
    path = bundle_dir(case_id) / "phoenix_registration" / "phoenix_cells_registered.csv"
    return path if path.is_file() else None


def _coordinate_source(case_id: str) -> tuple[Path, str, str, str]:
    registered = _registered_cells_path(case_id)
    if registered:
        return registered, "thumb_x", "thumb_y", "registered"
    return bundle_dir(case_id) / "phoenix_cells.csv", "x", "y", "phoenix_raw"


def _bounds_for_source(case_id: str, coord_source: str) -> dict[str, float]:
    if coord_source == "registered":
        thumb_w, thumb_h = thumbnail_size(case_id)
        return {"xMin": 0.0, "yMin": 0.0, "xMax": float(thumb_w), "yMax": float(thumb_h)}

    summary = load_summary(case_id)
    extent = summary.get("spatial_extent") or summary.get("spatialBounds") or {}
    return {
        "xMin": float(extent.get("x_min", extent.get("xMin", 0))),
        "yMin": float(extent.get("y_min", extent.get("yMin", 0))),
        "xMax": float(extent.get("x_max", extent.get("xMax", 1))),
        "yMax": float(extent.get("y_max", extent.get("yMax", 1))),
    }


def _available_genes(case_id: str) -> list[str]:
    return [row["gene"] for row in load_gene_summary(case_id)]


def _phoenix_to_thumbnail(x_phx: float, y_phx: float, case_id: str) -> tuple[float, float]:
    if str(PHOENIX_DIR) not in sys.path:
        sys.path.insert(0, str(PHOENIX_DIR))
    from coordinate_map import DEFAULT_TCGA_MAP, slide_dimensions

    summary = load_summary(case_id)
    coord_map_dict = summary.get("coordinate_map")
    if coord_map_dict:
        from coordinate_map import PhoenixCoordinateMap

        coord_map = PhoenixCoordinateMap(**{k: coord_map_dict[k] for k in (
            "magnification_scale", "swap_axes", "offset_x", "offset_y", "flip_x", "flip_y"
        )})
    else:
        coord_map = DEFAULT_TCGA_MAP

    reg_path = bundle_dir(case_id) / "phoenix_registration" / "registration.json"
    if reg_path.is_file():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        coord_map_dict = reg.get("coordinate_map")
        if coord_map_dict:
            from coordinate_map import PhoenixCoordinateMap

            coord_map = PhoenixCoordinateMap(**{k: coord_map_dict[k] for k in (
                "magnification_scale", "swap_axes", "offset_x", "offset_y", "flip_x", "flip_y"
            )})

    slide_name = summary.get("slide") or summary.get("gdc_slide", {}).get("file_name", "")
    wsi_root = REPO_ROOT / "data/tcga_lung/WSI"
    matches = sorted(wsi_root.rglob(f"*{case_id}*.svs"))
    if not matches and slide_name:
        matches = sorted(wsi_root.rglob(f"*{slide_name}*"))
    if not matches:
        raise FileNotFoundError(f"No WSI found for {case_id!r}; run registration or provide SVS")
    slide_wh = slide_dimensions(matches[0])
    thumb_wh = thumbnail_size(case_id)
    return coord_map.phoenix_to_thumbnail(x_phx, y_phx, slide_wh, thumb_wh)


def get_expression(case_id: str, gene: str) -> dict[str, Any]:
    genes = _available_genes(case_id)
    if gene not in genes:
        raise KeyError(f"Gene {gene!r} not in PHOENIX panel for {case_id}")

    cells_path, x_col, y_col, coord_source = _coordinate_source(case_id)
    bounds = _bounds_for_source(case_id, coord_source)
    xs: list[float] = []
    ys: list[float] = []
    values: list[float] = []

    with cells_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            x_val = float(row[x_col])
            y_val = float(row[y_col])
            if coord_source == "phoenix_raw":
                x_val, y_val = _phoenix_to_thumbnail(x_val, y_val, case_id)
            xs.append(x_val)
            ys.append(y_val)
            values.append(float(row[gene]))

    return {
        "caseId": case_id,
        "gene": gene,
        "nCells": len(values),
        "bounds": bounds,
        "coordinateSource": coord_source,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "mean": sum(values) / len(values) if values else 0.0,
        "x": xs,
        "y": ys,
        "value": values,
    }


def bundle_manifest(case_id: str) -> dict[str, Any]:
    summary = load_summary(case_id)
    genes = load_gene_summary(case_id)
    _, _, _, coord_source = _coordinate_source(case_id)
    bounds = _bounds_for_source(case_id, coord_source)
    thumb_w, thumb_h = thumbnail_size(case_id)
    crop = _preview_path(case_id, "tissue_crop")
    thumb = _preview_path(case_id, "thumbnail")
    registration = summary.get("registration") or {}
    asset_base = f"/data/tcga_lung/representative_patients/data_package/per_patient/{case_id}/slide_previews"

    return {
        "caseId": case_id,
        "study": summary.get("study"),
        "nCells": summary.get("n_cells", summary.get("nCells")),
        "nGenes": summary.get("n_genes", summary.get("nGenes")),
        "bounds": bounds,
        "thumbnailSize": {"width": thumb_w, "height": thumb_h},
        "coordinateSource": coord_source,
        "coordinateSystem": "thumbnail_px" if coord_source == "registered" else summary.get("coordinateSystem", "phoenix_20x"),
        "registration": registration.get("metrics"),
        "genes": [row["gene"] for row in genes],
        "topGenes": genes[:24],
        "assets": {
            "tissueCrop": f"{asset_base}/{crop.name}" if crop else None,
            "thumbnail": f"{asset_base}/{thumb.name}" if thumb else None,
        },
        "source": "PHOENIX TCGA atlas · inferred virtual spatial transcriptomics",
    }
