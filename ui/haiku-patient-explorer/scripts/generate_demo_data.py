#!/usr/bin/env python3
"""Build static JSON for the Haiku Patient Explorer UI (demo / pilot)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
UI_DATA = Path(__file__).resolve().parents[1] / "public" / "data"
SLIDES_META = ROOT / "data" / "tcga_lung" / "slides_metadata.tcga_lung.json"

ARCHETYPES = [
    "Immune Desert",
    "Immune Inflamed",
    "Myeloid/Treg-rich",
    "Stroma-high",
]
DRIVERS = ["EGFR", "KRAS G12C", "ALK", "WT"]
SIGNATURES = [
    "Treg",
    "Effector_cells",
    "Macrophages",
    "CAF",
    "MDSC",
    "T_cells",
    "Checkpoint_inhibition",
    "Angiogenesis",
]


def _load_signature_matrix() -> tuple[list[str], np.ndarray]:
    """Synthetic TME signature matrix for demo UMAP (replace with Phoenix/GigaTIME outputs)."""
    rng = np.random.default_rng(42)
    ids = [f"TCGA-DEMO-{i:04d}" for i in range(200)]
    return ids, rng.normal(size=(200, len(SIGNATURES)))


def _umap_2d(matrix: np.ndarray) -> np.ndarray:
    try:
        import umap

        reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.25)
        return reducer.fit_transform(matrix)
    except Exception:
        from sklearn.decomposition import PCA

        pca = PCA(n_components=2, random_state=42)
        return pca.fit_transform(matrix)


def _assign_archetype(row: np.ndarray) -> str:
  scores = {
      "Immune Desert": -(row[0] if len(row) > 0 else 0) - (row[1] if len(row) > 1 else 0),
      "Immune Inflamed": (row[1] if len(row) > 1 else 0) + (row[5] if len(row) > 5 else 0),
      "Myeloid/Treg-rich": (row[0] if len(row) > 0 else 0) + (row[2] if len(row) > 2 else 0),
      "Stroma-high": (row[3] if len(row) > 3 else 0),
  }
  return max(scores, key=scores.get)


def build_patients_embedding() -> dict:
    slides = json.loads(SLIDES_META.read_text())
    cases = sorted({s["case_submitter_id"] for s in slides})
    sig_ids, sig_matrix = _load_signature_matrix()
    coords = _umap_2d(sig_matrix)

    # Map available signature rows onto TCGA cases (cycle if fewer signatures than cases)
    rng = random.Random(42)
    patients = []
    for i, case_id in enumerate(cases):
        sig_idx = i % len(sig_ids)
        row = sig_matrix[sig_idx]
        archetype = _assign_archetype(row)
        driver = rng.choices(DRIVERS, weights=[22, 13, 5, 60], k=1)[0]
        alive = rng.random() > 0.42
        sig_map = {SIGNATURES[j]: float(row[j]) if j < len(row) else 0.0 for j in range(len(SIGNATURES))}
        # reuse umap coord from signature row, add tiny jitter per case
        ux = float(coords[sig_idx, 0]) + rng.uniform(-0.15, 0.15)
        uy = float(coords[sig_idx, 1]) + rng.uniform(-0.15, 0.15)
        patients.append(
            {
                "case_id": case_id,
                "project_id": next(s["project_id"] for s in slides if s["case_submitter_id"] == case_id),
                "umap_x": ux,
                "umap_y": uy,
                "archetype": archetype,
                "driver": driver,
                "os_status": "alive" if alive else "deceased",
                "signatures": sig_map,
            }
        )

    return {
        "meta": {
            "n_patients": len(patients),
            "source": "TCGA lung diagnostic slides + synthetic TME signature demo (Phoenix/GigaTIME)",
            "projection": "UMAP (or PCA fallback) on signature matrix",
            "archetypes": ARCHETYPES,
            "drivers": DRIVERS,
            "color_signatures": SIGNATURES,
        },
        "patients": patients,
    }


def build_spatial_demo(case_id: str | None = None) -> dict:
    rng = np.random.default_rng(7)
    grid = 48
    tiles = []
    for gy in range(grid):
        for gx in range(grid):
            cx, cy = gx / grid - 0.5, gy / grid - 0.5
            dist = (cx**2 + cy**2) ** 0.5
            treg = max(0, 0.8 - dist + rng.normal(0, 0.08))
            effector = max(0, dist * 0.6 + rng.normal(0, 0.1) if dist > 0.2 else 0.1)
            mac = max(0, 0.5 - abs(cx) + rng.normal(0, 0.07))
            tiles.append(
                {
                    "x": int(gx * 512),
                    "y": int(gy * 512),
                    "Treg": float(np.clip(treg, 0, 1)),
                    "Effector_cells": float(np.clip(effector, 0, 1)),
                    "Macrophages": float(np.clip(mac, 0, 1)),
                    "CAF": float(np.clip(0.3 + cy * 0.4 + rng.normal(0, 0.05), 0, 1)),
                }
            )
    return {
        "case_id": case_id or "TCGA-05-4244",
        "signature": "Treg",
        "tile_size": 256,
        "tiles": tiles,
        "note": "Demo spatial scores — replace with predict_spatial.py output",
    }


def main() -> None:
    UI_DATA.mkdir(parents=True, exist_ok=True)
    embedding = build_patients_embedding()
    (UI_DATA / "patients_embedding.json").write_text(json.dumps(embedding, indent=2))

    demo_case = embedding["patients"][0]["case_id"]
    spatial = build_spatial_demo(demo_case)
    (UI_DATA / "spatial_heatmap_demo.json").write_text(json.dumps(spatial, indent=2))
    print(f"Wrote {len(embedding['patients'])} patients -> {UI_DATA / 'patients_embedding.json'}")
    print(f"Wrote spatial demo -> {UI_DATA / 'spatial_heatmap_demo.json'}")


if __name__ == "__main__":
    main()
