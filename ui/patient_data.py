"""Load and normalize representative TCGA lung patient metadata for the UI."""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PATIENTS_JSON = REPO_ROOT / "data/tcga_lung/representative_patients/representative_20_patients.json"

STRATUM_LAYOUT: dict[str, dict[str, Any]] = {
    "TCGA-LUAD|non_smoker": {
        "x": 3.0,
        "y": 3.0,
        "tmeArchetype": "Immune Inflamed",
        "immuneStatus": "Immune Hot",
    },
    "TCGA-LUAD|smoker": {
        "x": 4.0,
        "y": -2.0,
        "tmeArchetype": "Stroma-high",
        "immuneStatus": "Immune Cold",
    },
    "TCGA-LUSC|non_smoker": {
        "x": -4.0,
        "y": 2.0,
        "tmeArchetype": "Immune Desert",
        "immuneStatus": "Immune Cold",
    },
    "TCGA-LUSC|smoker": {
        "x": -2.0,
        "y": -3.0,
        "tmeArchetype": "Myeloid/Treg-rich",
        "immuneStatus": "Immune Excluded",
    },
}

GENE_COLORS = {
    "EGFR": "#4f8ef7",
    "KRAS": "#e05c5c",
    "ALK": "#7c5cbf",
    "TP53": "#f5c542",
    "STK11": "#3ecf8e",
    "KEAP1": "#e05c5c",
    "NOTCH2": "#7c5cbf",
    "CDKN2A": "#6b7280",
    "WT": "#6b7280",
}

TREATMENT_COLOR_KEYS = (
    "platinum_multi",
    "platinum",
    "taxane",
    "tki",
    "advanced_systemic",
    "multi_agent",
    "single_agent",
    "chemo_unspecified",
    "rt_unspecified",
    "unspecified",
    "unknown",
)


def _split_field(value: Any) -> list[str]:
    if value in (None, "", "—"):
        return []
    text = str(value).strip()
    if text.lower() == "missing":
        return []
    return [part.strip() for part in text.split(";") if part.strip() and part.strip().lower() != "missing"]


def _format_list(values: list[str], *, fallback: str = "Not documented") -> str:
    return "; ".join(values) if values else fallback


def _classify_treatment(agents: list[str], types: list[str]) -> tuple[str, str]:
    agents_lower = [agent.lower() for agent in agents]
    types_lower = [item.lower() for item in types]

    has_platinum = any(token in agent for agent in agents_lower for token in ("cisplatin", "carboplatin"))
    has_taxane = any(token in agent for agent in agents_lower for token in ("paclitaxel", "docetaxel"))
    has_tki = any("tyrosine kinase" in agent or "tki" in agent for agent in agents_lower)
    has_advanced = any(
        token in agent for agent in agents_lower for token in ("bevacizumab", "pemetrexed", "gemcitabine", "etoposide")
    )

    if not agents and not types:
        return "unknown", "Not documented"

    if not agents:
        if any("chemotherapy" in item for item in types_lower):
            return "chemo_unspecified", "Chemo (agents NOS)"
        if any("radiation" in item for item in types_lower):
            return "rt_unspecified", "Radiation ± systemic"
        if any("immunotherapy" in item for item in types_lower):
            return "advanced_systemic", "Immunotherapy (agents NOS)"
        return "unspecified", "Treatment (agents NOS)"

    if has_platinum and len(agents) >= 2:
        return "platinum_multi", "Platinum multi-agent"
    if has_platinum:
        return "platinum", "Platinum chemo"
    if has_tki:
        return "tki", "TKI / targeted"
    if has_advanced and len(agents) >= 2:
        return "advanced_systemic", "Advanced systemic"
    if has_taxane:
        return "taxane", "Taxane-based"
    if len(agents) >= 2:
        return "multi_agent", "Multi-agent chemo"
    return "single_agent", agents[0]


def _format_disease_response(values: list[str]) -> str:
    if not values:
        return "Not documented"
    mapping = {
        "TF-Tumor Free": "Tumor free",
        "WT-With Tumor": "With tumor",
    }
    return "; ".join(mapping.get(value, value) for value in values)


def _outcome_tier(raw: dict[str, Any], os_status: str) -> tuple[str, str]:
    responses = _split_field(raw.get("disease_response"))
    progression = str(raw.get("progression_or_recurrence") or "").strip().lower()

    has_with_tumor = any(item.startswith("WT-") or "with tumor" in item.lower() for item in responses)
    has_tumor_free = any(item.startswith("TF-") or "tumor free" in item.lower() for item in responses)

    if os_status == "deceased":
        return "unfavorable", "Unfavorable"
    if has_with_tumor and progression == "yes":
        return "unfavorable", "Unfavorable"
    if has_tumor_free and not has_with_tumor:
        return "favorable", "Favorable"
    if has_tumor_free and has_with_tumor:
        return "mixed", "Mixed"
    if has_with_tumor:
        return "mixed", "Mixed"
    if os_status == "alive" and not responses:
        return "unknown", "Unknown"
    return "unknown", "Unknown"


def _outcome_summary(raw: dict[str, Any], os_status: str, os_months: float) -> str:
    status = "Deceased" if os_status == "deceased" else "Alive"
    months = f"{os_months} mo" if os_months else "—"
    response = _format_disease_response(_split_field(raw.get("disease_response")))
    progression = str(raw.get("progression_or_recurrence") or "").strip()
    parts = [f"{status} · {months}", f"Response: {response}"]
    if progression and progression.lower() != "missing":
        parts.append(f"Recurrence: {progression.capitalize()}")
    return " · ".join(parts)


def _seeded_unit(case_id: str, salt: str) -> float:
    digest = hashlib.md5(f"{case_id}:{salt}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _jitter(case_id: str) -> tuple[float, float]:
    return (_seeded_unit(case_id, "x") - 0.5) * 1.6, (_seeded_unit(case_id, "y") - 0.5) * 1.6


def _format_sex(value: str | None) -> str:
    if not value:
        return "Unknown"
    return value.strip().capitalize()


def _subtype(project_id: str) -> str:
    if "LUAD" in project_id:
        return "LUAD"
    if "LUSC" in project_id:
        return "LUSC"
    return project_id.replace("TCGA-", "")


def _os_status(raw: dict[str, Any]) -> str:
    vital = str(raw.get("vital_status") or "").lower()
    if vital in {"dead", "deceased"}:
        return "deceased"
    if raw.get("survival_event") == 1:
        return "deceased"
    return "alive"


def _driver_mutation(genes: list[str]) -> str:
    if not genes:
        return "WT"
    gene = genes[0].upper()
    if gene == "KRAS":
        return "KRAS G12C"
    return gene


def _pathogenic_label(genes: list[str]) -> str:
    if not genes:
        return "None detected"
    return "; ".join(genes)


def _cluster_label(stratum: str) -> str:
    parts = stratum.split("|")
    if len(parts) == 2:
        project, smoking = parts
        smoking_label = "non-smoker" if smoking == "non_smoker" else "smoker"
        return f"{project.replace('TCGA-', '')} · {smoking_label}"
    return stratum


@lru_cache(maxsize=1)
def load_representative_patients() -> dict[str, Any]:
    if not PATIENTS_JSON.is_file():
        raise FileNotFoundError(f"Missing patient metadata: {PATIENTS_JSON}")
    with PATIENTS_JSON.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    raw_patients = payload.get("patients") or []
    patients = [_to_ui_patient(row) for row in raw_patients]
    patients.sort(key=lambda item: item["selectionRank"])
    default_case_id = patients[0]["caseId"] if patients else None
    return {
        "defaultCaseId": default_case_id,
        "count": len(patients),
        "source": str(PATIENTS_JSON.relative_to(REPO_ROOT)),
        "selectionNotes": payload.get("selection_notes"),
        "patients": patients,
    }


def _to_ui_patient(raw: dict[str, Any]) -> dict[str, Any]:
    case_id = raw["case_submitter_id"]
    genes = list(raw.get("important_gene_mutations") or [])
    stratum = raw.get("stratum") or "unknown"
    layout = STRATUM_LAYOUT.get(stratum, STRATUM_LAYOUT["TCGA-LUAD|smoker"])
    jx, jy = _jitter(case_id)
    age = raw.get("age_at_diagnosis_years")
    age_int = int(round(age)) if isinstance(age, (int, float)) and not math.isnan(age) else None
    os_months = 0.0
    survival_days = raw.get("survival_time_days")
    if isinstance(survival_days, (int, float)) and not math.isnan(survival_days):
        os_months = round(float(survival_days) / 30.44, 1)

    driver = _driver_mutation(genes)
    subtype = _subtype(raw.get("project_id", ""))
    os_status = _os_status(raw)
    agents = _split_field(raw.get("therapeutic_agents"))
    treatment_types = _split_field(raw.get("treatment_types"))
    treatment_key, treatment_received = _classify_treatment(agents, treatment_types)
    outcome_key, outcome_label = _outcome_tier(raw, os_status)

    return {
        "caseId": case_id,
        "x": layout["x"] + jx,
        "y": layout["y"] + jy,
        "summary": {
            "caseId": case_id,
            "subtype": subtype,
            "driverMutation": _pathogenic_label(genes) if genes else "None detected",
            "age": age_int,
            "sex": _format_sex(raw.get("sex")),
        },
        "tmeArchetype": layout["tmeArchetype"],
        "immuneStatus": layout["immuneStatus"],
        "driverMutation": driver,
        "pathogenicMutations": _pathogenic_label(genes),
        "osStatus": os_status,
        "osMonths": os_months,
        "subtype": subtype,
        "stage": raw.get("ajcc_pathologic_stage") or "Unknown",
        "smokingGroup": raw.get("smoking_group") or raw.get("tobacco_smoking_status") or "Unknown",
        "stratum": stratum,
        "cluster": _cluster_label(stratum),
        "clusterConfidence": max(72, 100 - int(raw.get("selection_rank", 1)) * 2),
        "signatures": {
            "Treg": round(_seeded_unit(case_id, "treg"), 3),
            "Effector_cells": round(_seeded_unit(case_id, "effector"), 3),
        },
        "selectionRank": int(raw.get("selection_rank", 0)),
        "vitalStatus": raw.get("vital_status") or "Unknown",
        "therapeuticAgents": _format_list(agents),
        "treatmentTypes": _format_list(treatment_types, fallback="Not documented"),
        "treatmentAgents": _format_list(agents),
        "treatmentModalities": _format_list(treatment_types, fallback="Not documented"),
        "treatmentKey": treatment_key,
        "treatmentReceived": treatment_received,
        "outcomeKey": outcome_key,
        "outcomeLabel": outcome_label,
        "outcomeSummary": _outcome_summary(raw, os_status, os_months),
        "diseaseResponse": _format_disease_response(_split_field(raw.get("disease_response"))),
        "progressionStatus": raw.get("progression_or_recurrence") or "Not documented",
        "geneColors": {gene: GENE_COLORS.get(gene, "#6b7280") for gene in genes},
    }


def get_patient(case_id: str) -> dict[str, Any] | None:
    cohort = load_representative_patients()
    normalized = case_id.strip().upper()
    for patient in cohort["patients"]:
        if patient["caseId"].upper() == normalized:
            return patient
    return None


def nearest_patients(case_id: str, limit: int = 3) -> list[dict[str, Any]]:
    target = get_patient(case_id)
    if not target:
        return []

    cohort = load_representative_patients()

    def score(other: dict[str, Any]) -> float:
        if other["caseId"] == target["caseId"]:
            return -1.0
        same_stratum = 1.0 if other["stratum"] == target["stratum"] else 0.0
        shared = set(other["pathogenicMutations"].split("; ")) & set(
            target["pathogenicMutations"].split("; ")
        )
        shared.discard("None detected")
        mutation_score = len(shared) * 0.35
        distance = math.hypot(other["x"] - target["x"], other["y"] - target["y"])
        proximity = max(0.0, 1.0 - distance / 6.0)
        return same_stratum + mutation_score + proximity

    ranked = sorted(cohort["patients"], key=score, reverse=True)
    results: list[dict[str, Any]] = []
    for other in ranked:
        if other["caseId"] == target["caseId"]:
            continue
        sim = min(99, int(round(score(other) * 38 + 58)))
        results.append(
            {
                "caseId": other["caseId"],
                "meta": f"{other['driverMutation']} · {other['stage']}",
                "similarity": sim,
            }
        )
        if len(results) >= limit:
            break
    return results
