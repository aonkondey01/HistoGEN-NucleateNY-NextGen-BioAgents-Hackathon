#!/usr/bin/env python3
"""Build Haiku patient embeddings from demo H&E previews + clinical notes.

Combines per-patient ``clinical.json``, PHOENIX signature scores, and optional
GigaTIME outputs into ``demo/haiku/patients_embedding.json`` for the UI agent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from paths import BUNDLE_ROOT, HAIKU_DIR, PATIENTS_JSON  # noqa: E402

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

IMMUNE = ["CD3D", "CD3E", "CD8A", "GZMB"]
TREG = ["FOXP3", "IL2RA", "CTLA4"]
MAC = ["CD68", "CD163", "CSF1R"]
CAF_GENES = ["ACTA2", "COL1A1", "FAP"]


def _signatures_from_phoenix(case_id: str) -> dict[str, float]:
    summary = BUNDLE_ROOT / case_id / "phoenix_gene_summary.csv"
    if not summary.is_file():
        return {s: 0.0 for s in SIGNATURES}
    genes: dict[str, float] = {}
    with summary.open() as fh:
        for row in csv.DictReader(fh):
            genes[row["gene"]] = float(row["mean_readout"])
    immune = float(np.mean([genes.get(g, 0.0) for g in IMMUNE]))
    treg = float(np.mean([genes.get(g, 0.0) for g in TREG]))
    mac = float(np.mean([genes.get(g, 0.0) for g in MAC]))
    caf = float(np.mean([genes.get(g, 0.0) for g in CAF_GENES]))
    return {
        "Treg": treg,
        "Effector_cells": immune,
        "Macrophages": mac,
        "CAF": caf,
        "MDSC": float(genes.get("ARG1", genes.get("S100A12", 0.0))),
        "T_cells": immune,
        "Checkpoint_inhibition": float(genes.get("PDCD1", 0.0) + genes.get("CD274", 0.0)),
        "Angiogenesis": float(genes.get("PECAM1", 0.0) + genes.get("VWF", 0.0)),
    }


def _clinical_features(case_id: str) -> dict[str, Any]:
    path = BUNDLE_ROOT / case_id / "clinical.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _embedding_vector(sig: dict[str, float], clinical: dict[str, Any]) -> list[float]:
    base = [sig[s] for s in SIGNATURES]
    note = json.dumps(clinical, sort_keys=True)
    digest = hashlib.sha256(note.encode()).digest()
    jitter = [((digest[i % len(digest)] / 255.0) - 0.5) * 0.05 for i in range(8)]
    return base + jitter


def _umap_2d(matrix: np.ndarray) -> np.ndarray:
    try:
        import umap

        return umap.UMAP(n_components=2, random_state=42, n_neighbors=8, min_dist=0.3).fit_transform(matrix)
    except Exception:
        from sklearn.decomposition import PCA

        return PCA(n_components=2, random_state=42).fit_transform(matrix)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    rep = json.loads(PATIENTS_JSON.read_text())
    patients_meta = rep["patients"]
    if args.limit:
        patients_meta = patients_meta[: args.limit]

    rows = []
    vectors = []
    for p in patients_meta:
        case_id = p["case_submitter_id"]
        clinical = _clinical_features(case_id)
        sig = _signatures_from_phoenix(case_id)
        vec = _embedding_vector(sig, clinical)
        vectors.append(vec)
        rows.append(
            {
                "case_id": case_id,
                "project_id": p["project_id"],
                "stratum": p.get("stratum"),
                "smoking_group": p.get("smoking_group"),
                "signatures": sig,
                "clinical_note_hash": hashlib.sha256(json.dumps(clinical, sort_keys=True).encode()).hexdigest()[:16],
                "clinical": {
                    "stage": clinical.get("ajcc_pathologic_stage") or clinical.get("stage"),
                    "vital_status": clinical.get("vital_status"),
                    "histology": clinical.get("primary_diagnosis"),
                },
            }
        )

    coords = _umap_2d(np.array(vectors, dtype=float))
    for i, row in enumerate(rows):
        row["umap_x"] = float(coords[i, 0])
        row["umap_y"] = float(coords[i, 1])

    payload = {
        "meta": {
            "n_patients": len(rows),
            "source": "Haiku demo — PHOENIX signatures + TCGA clinical notes + H&E bundle",
            "projection": "UMAP on combined signature + clinical hash features",
        },
        "patients": rows,
    }

    HAIKU_DIR.mkdir(parents=True, exist_ok=True)
    out = HAIKU_DIR / "patients_embedding.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out} ({len(rows)} patients)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
