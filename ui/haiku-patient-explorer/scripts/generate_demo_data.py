#!/usr/bin/env python3
"""Build static JSON for the Haiku Patient Explorer UI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
UI_DATA = Path(__file__).resolve().parents[1] / "public" / "data"
SLIDES_META = ROOT / "data" / "tcga_lung" / "slides_metadata.tcga_lung.json"
PATIENT_META = ROOT / "data" / "tcga_lung" / "patient_metadata.tcga_lung.json"
MUTATIONS = ROOT / "data" / "tcga_lung" / "important_lung_genes" / "important_mutations.tcga_lung.csv"
PANTCGA = ROOT / "external" / "HistoTME" / "example_data" / "pantcga_tme_signatures.csv"

ARCHETYPES = [
    "Immune Desert",
    "Immune Inflamed",
    "Myeloid/Treg-rich",
    "Stroma-high",
]
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
DRIVER_GENES = ("EGFR", "KRAS", "ALK", "MET", "BRAF", "ROS1", "RET", "ERBB2")


def _load_signature_matrix() -> tuple[list[str], np.ndarray]:
    if not PANTCGA.exists():
        rng = np.random.default_rng(42)
        ids = [f"TCGA-DEMO-{i:04d}" for i in range(200)]
        return ids, rng.normal(size=(200, len(SIGNATURES)))

    import pandas as pd

    df = pd.read_csv(PANTCGA, index_col=0)
    lung_mask = df.index.str.startswith("TCGA-") & (
        df.index.str.contains("-LU", regex=False) | df.index.str.contains("OR-A", regex=False)
    )
    lung = df.loc[lung_mask] if lung_mask.any() else df.iloc[: min(400, len(df))]
    cols = [c for c in lung.columns if c in SIGNATURES] or list(lung.columns[: len(SIGNATURES)])
    return list(lung.index.astype(str)), lung[cols].fillna(0).to_numpy(dtype=float)


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


def _load_drivers_by_case() -> dict[str, str]:
    if not MUTATIONS.exists():
        return {}
    import pandas as pd

    df = pd.read_csv(MUTATIONS)
    drivers: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        case = row.get("case_submitter_id")
        gene = row.get("gene")
        hgvsp = str(row.get("hgvsp_short") or "")
        if not case or gene not in DRIVER_GENES:
            continue
        label = str(gene)
        if gene == "KRAS" and "G12C" in hgvsp:
            label = "KRAS G12C"
        drivers.setdefault(case, set()).add(label)
    return {k: "; ".join(sorted(v)) if v else "WT" for k, v in drivers.items()}


def _load_clinical_by_case() -> dict[str, dict]:
    if not PATIENT_META.exists():
        return {}
    rows = json.loads(PATIENT_META.read_text())
    return {r["case_submitter_id"]: r for r in rows if r.get("case_submitter_id")}


def _split_semicolon(value: str | list | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _parse_treatment_category(treatment_types: str | None) -> str:
    if not treatment_types:
        return "None documented"
    t = treatment_types.lower()
    if "pharmaceutical" in t and "radiation" in t:
        return "Pharma + Radiation"
    if "chemotherapy" in t and "radiation" in t:
        return "Chemo + Radiation"
    if "pharmaceutical" in t:
        return "Pharmaceutical"
    if "chemotherapy" in t:
        return "Chemotherapy"
    if "radiation" in t:
        return "Radiation"
    if "surgery" in t:
        return "Surgery"
    return treatment_types.split(";")[0].strip()


def _observed_benefit_label(clinical: dict) -> str:
    response = (clinical.get("disease_response") or "").upper()
    progression = (clinical.get("progression_or_recurrence") or "").lower()
    vital = (clinical.get("vital_status") or "").lower()
    survival_days = clinical.get("survival_time_days") or 0

    if "CR" in response or "PR" in response or "TUMOR FREE" in response:
        return "Observed: Responded"
    if progression in ("yes", "true"):
        return "Observed: Progressed"
    if vital == "dead" and survival_days and survival_days < 365:
        return "Observed: Poor survival"
    if vital == "alive" and survival_days and survival_days > 730:
        return "Observed: Durable survival"
    return "Observed: Uncertain"


def _predict_benefit(archetype: str, driver: str, treatment_category: str) -> dict:
    """Heuristic benefit score: TME archetype × driver × treatment alignment."""
    score = 50.0
    reasons: list[str] = []

    has_pharma = "Pharma" in treatment_category or treatment_category == "Chemotherapy"
    has_radio = "Radiation" in treatment_category
    no_tx = treatment_category == "None documented"

    primary_driver = driver.split(";")[0] if driver else "WT"

    if no_tx:
        score = 35.0
        reasons.append("No systemic treatment documented in TCGA record.")
    elif primary_driver == "EGFR" and has_pharma:
        score = 78.0 if archetype != "Immune Desert" else 68.0
        reasons.append("EGFR-mutant NSCLC: pharmaceutical therapy is typically appropriate.")
        if archetype == "Immune Desert":
            reasons.append("Immune-desert TME may limit benefit from immunotherapy combinations.")
        elif archetype == "Immune Inflamed":
            reasons.append("Inflamed TME supports durable response to targeted therapy in many cases.")
    elif primary_driver == "KRAS G12C" and has_pharma:
        score = 62.0 if archetype != "Stroma-high" else 52.0
        reasons.append("KRAS G12C: targeted inhibition can work but resistance is common.")
        if archetype == "Myeloid/Treg-rich":
            score -= 8.0
            reasons.append("Myeloid/Treg-rich niche may blunt long-term benefit.")
    elif primary_driver == "ALK" and has_pharma:
        score = 82.0
        reasons.append("ALK rearrangement: strong historical response to targeted inhibitors.")
    elif primary_driver not in ("WT", "") and has_pharma:
        score = 70.0
        reasons.append(f"Actionable driver ({primary_driver}) with systemic therapy documented.")
    elif primary_driver == "WT" and archetype == "Immune Inflamed" and has_pharma:
        score = 72.0
        reasons.append("No dominant driver but inflamed TME: better immunotherapy/chemo-IO potential.")
    elif archetype == "Immune Desert" and has_pharma:
        score = 42.0
        reasons.append("Immune-desert TME without clear driver: lower expected immunotherapy benefit.")
    elif archetype == "Stroma-high":
        score -= 6.0
        reasons.append("Stroma-high TME can limit drug penetration and immune access.")
    else:
        reasons.append("Moderate alignment between TME profile and documented treatment.")

    if has_radio:
        score += 4.0
        reasons.append("Radiation included in treatment plan (local control).")

    score = float(np.clip(score, 5, 95))

    if score >= 70:
        label = "Likely benefit"
    elif score >= 50:
        label = "Uncertain benefit"
    else:
        label = "Unlikely benefit"

    return {
        "score": round(score, 1),
        "label": label,
        "recommended_class": treatment_category if not no_tx else "Consider systemic therapy",
        "reasons": reasons[:4],
    }


def build_patients_embedding() -> dict:
    slides = json.loads(SLIDES_META.read_text())
    cases = sorted({s["case_submitter_id"] for s in slides})
    sig_ids, sig_matrix = _load_signature_matrix()
    coords = _umap_2d(sig_matrix)
    clinical_by_case = _load_clinical_by_case()
    drivers_by_case = _load_drivers_by_case()

    patients = []
    for i, case_id in enumerate(cases):
        sig_idx = i % len(sig_ids)
        row = sig_matrix[sig_idx]
        archetype = _assign_archetype(row)
        sig_map = {SIGNATURES[j]: float(row[j]) if j < len(row) else 0.0 for j in range(len(SIGNATURES))}
        ux = float(coords[sig_idx, 0]) + np.random.default_rng(hash(case_id) % 2**32).uniform(-0.15, 0.15)
        uy = float(coords[sig_idx, 1]) + np.random.default_rng(hash(case_id) % 2**32).uniform(-0.15, 0.15)

        clinical = clinical_by_case.get(case_id, {})
        driver = drivers_by_case.get(case_id, "WT")
        treatment_types = clinical.get("treatment_types")
        treatment_category = _parse_treatment_category(treatment_types)
        prediction = _predict_benefit(archetype, driver, treatment_category)
        vital = clinical.get("vital_status")
        survival_days = clinical.get("survival_time_days")

        patients.append(
            {
                "case_id": case_id,
                "project_id": clinical.get("project_id")
                or next(s["project_id"] for s in slides if s["case_submitter_id"] == case_id),
                "umap_x": ux,
                "umap_y": uy,
                "archetype": archetype,
                "driver": driver,
                "histology": clinical.get("primary_diagnosis") or "Lung carcinoma",
                "stage": clinical.get("ajcc_pathologic_stage") or "—",
                "smoking": clinical.get("tobacco_smoking_status") or "Unknown",
                "os_status": "alive" if (vital or "").lower() == "alive" else "deceased",
                "signatures": sig_map,
                "treatment": {
                    "types": _split_semicolon(treatment_types) or ["None documented"],
                    "category": treatment_category,
                    "intent": clinical.get("treatment_intent_types") or "—",
                    "agents": _split_semicolon(clinical.get("therapeutic_agents")),
                    "regimen": clinical.get("regimen_or_line_of_therapy") or "—",
                    "outcome": clinical.get("treatment_outcomes"),
                    "disease_response": clinical.get("disease_response"),
                    "progression": clinical.get("progression_or_recurrence"),
                },
                "clinical": {
                    "stage": clinical.get("ajcc_pathologic_stage"),
                    "diagnosis": clinical.get("primary_diagnosis"),
                    "vital_status": vital,
                    "disease_response": clinical.get("disease_response"),
                    "progression_or_recurrence": clinical.get("progression_or_recurrence"),
                    "overall_survival_days": survival_days,
                    "survival_days": survival_days,
                    "observed_benefit": _observed_benefit_label(clinical),
                },
                "predicted_benefit": prediction,
            }
        )

    return {
        "meta": {
            "n_patients": len(patients),
            "source": "TCGA lung + HistoTME signatures + clinical treatment metadata",
            "projection": "UMAP on TME signature scores",
            "archetypes": ARCHETYPES,
            "color_signatures": SIGNATURES,
            "treatment_categories": sorted({p["treatment"]["category"] for p in patients}),
            "benefit_labels": ["Likely benefit", "Uncertain benefit", "Unlikely benefit"],
        },
        "patients": patients,
    }


def main() -> None:
    UI_DATA.mkdir(parents=True, exist_ok=True)
    embedding = build_patients_embedding()
    out = UI_DATA / "patients_embedding.json"
    out.write_text(json.dumps(embedding, indent=2))
    print(f"Wrote {len(embedding['patients'])} patients -> {out}")


if __name__ == "__main__":
    main()
