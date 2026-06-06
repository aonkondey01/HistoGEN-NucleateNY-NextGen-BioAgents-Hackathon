#!/usr/bin/env python3
"""Build Haiku UI JSON for the 20 representative TCGA lung patients."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
UI_DATA = Path(__file__).resolve().parents[1] / "public" / "data"
REP_JSON = ROOT / "data" / "tcga_lung" / "representative_patients" / "representative_20_patients.json"
REP_CSV = ROOT / "data" / "tcga_lung" / "representative_patients" / "representative_20_patients.csv"
BUNDLE_ROOT = ROOT / "data" / "tcga_lung" / "representative_patients" / "data_package" / "per_patient"
PANTCGA = ROOT / "external" / "HistoTME" / "example_data" / "pantcga_tme_signatures.csv"

ARCHETYPES = ["Immune Desert", "Immune Inflamed", "Myeloid/Treg-rich", "Stroma-high"]
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


def _umap_2d(matrix: np.ndarray) -> np.ndarray:
    try:
        import umap

        return umap.UMAP(n_components=2, random_state=42, n_neighbors=8, min_dist=0.3).fit_transform(matrix)
    except Exception:
        from sklearn.decomposition import PCA

        return PCA(n_components=2, random_state=42).fit_transform(matrix)


def _assign_archetype(sig: dict[str, float]) -> str:
    scores = {
        "Immune Desert": -(sig.get("Treg", 0) + sig.get("Effector_cells", 0)),
        "Immune Inflamed": sig.get("Effector_cells", 0) + sig.get("T_cells", 0),
        "Myeloid/Treg-rich": sig.get("Treg", 0) + sig.get("Macrophages", 0),
        "Stroma-high": sig.get("CAF", 0),
    }
    return max(scores, key=scores.get)


def _driver_from_row(row: dict) -> str:
    muts = (row.get("important_gene_mutations") or "").strip()
    if not muts:
        return "WT"
    first = muts.split(";")[0].strip()
    if first == "KRAS":
        return "KRAS G12C"
    if first in ("EGFR", "ALK"):
        return first
    return first or "WT"


def _signatures_for_case(case_id: str, pantcga_row: dict[str, float] | None) -> dict[str, float]:
    summary = BUNDLE_ROOT / case_id / "phoenix_gene_summary.csv"
    if summary.exists():
        genes = {}
        with summary.open() as fh:
            for row in csv.DictReader(fh):
                genes[row["gene"]] = float(row["mean_readout"])
        immune = np.mean([genes.get(g, 0.0) for g in ("CD3D", "CD3E", "CD8A", "GZMB")])
        treg = np.mean([genes.get(g, 0.0) for g in ("FOXP3", "IL2RA", "CTLA4")])
        mac = np.mean([genes.get(g, 0.0) for g in ("CD68", "CD163", "CSF1R")])
        caf = np.mean([genes.get(g, 0.0) for g in ("ACTA2", "COL1A1", "FAP")])
        return {
            "Treg": float(treg),
            "Effector_cells": float(immune),
            "Macrophages": float(mac),
            "CAF": float(caf),
            "MDSC": float(genes.get("ARG1", genes.get("S100A12", 0.0))),
            "T_cells": float(immune),
            "Checkpoint_inhibition": float(genes.get("PDCD1", 0.0) + genes.get("CD274", 0.0)),
            "Angiogenesis": float(genes.get("PECAM1", 0.0) + genes.get("VWF", 0.0)),
        }
    if pantcga_row:
        return {s: float(pantcga_row.get(s, 0.0)) for s in SIGNATURES}
    return {s: 0.0 for s in SIGNATURES}


def main() -> int:
    rep = json.loads(REP_JSON.read_text())
    rows = list(csv.DictReader(REP_CSV.open()))
    row_by_case = {r["case_submitter_id"]: r for r in rows}

    pantcga: dict[str, dict[str, float]] = {}
    if PANTCGA.exists():
        import pandas as pd

        df = pd.read_csv(PANTCGA, index_col=0)
        for idx in df.index.astype(str):
            pantcga[idx] = {c: float(df.loc[idx, c]) for c in df.columns if c in SIGNATURES}

    patients = []
    sig_matrix = []
    for p in rep["patients"]:
        case_id = p["case_submitter_id"]
        csv_row = row_by_case[case_id]
        sig = _signatures_for_case(case_id, pantcga.get(case_id))
        sig_matrix.append([sig[s] for s in SIGNATURES])
        patients.append(
            {
                "case_id": case_id,
                "project_id": p["project_id"],
                "archetype": _assign_archetype(sig),
                "driver": _driver_from_row(csv_row),
                "os_status": "alive" if str(csv_row.get("vital_status", "")).lower() == "alive" else "deceased",
                "signatures": sig,
                "stratum": p.get("stratum"),
                "smoking_group": p.get("smoking_group"),
                "has_slide_thumb": (UI_DATA / "slides" / f"{case_id}.thumbnail.png").exists(),
                "has_spatial": (UI_DATA / f"spatial_heatmap_{case_id}.json").exists(),
            }
        )

    coords = _umap_2d(np.array(sig_matrix, dtype=float))
    for i, pt in enumerate(patients):
        pt["umap_x"] = float(coords[i, 0])
        pt["umap_y"] = float(coords[i, 1])

    embedding = {
        "meta": {
            "n_patients": len(patients),
            "source": "20 representative TCGA lung patients + PHOENIX/HistoTME signatures",
            "projection": "UMAP on PHOENIX-derived signature matrix",
            "archetypes": ARCHETYPES,
            "color_signatures": SIGNATURES,
        },
        "patients": patients,
    }

    UI_DATA.mkdir(parents=True, exist_ok=True)
    (UI_DATA / "patients_embedding.json").write_text(json.dumps(embedding, indent=2))

    # Index of available spatial heatmaps
    spatial_index = {
        p["case_id"]: f"/data/spatial_heatmap_{p['case_id']}.json"
        for p in patients
        if (UI_DATA / f"spatial_heatmap_{p['case_id']}.json").exists()
    }
    (UI_DATA / "spatial_heatmap_index.json").write_text(json.dumps(spatial_index, indent=2))

    print(f"Wrote {len(patients)} patients -> {UI_DATA / 'patients_embedding.json'}")
    print(f"Spatial heatmaps available for {len(spatial_index)} / {len(patients)} patients")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
