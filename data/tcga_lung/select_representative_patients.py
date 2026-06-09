#!/usr/bin/env python3
"""Select a diverse, cohort-representative patient subset from TCGA lung data.

Selection constraints:
* 10 LUAD + 10 LUSC patients
* 5 smokers + 5 lifelong non-smokers within each histology
* Maximize clinical and driver-mutation diversity while staying close to
  project-specific cohort distributions
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECTS = ("TCGA-LUAD", "TCGA-LUSC")

KEY_DRIVERS = {
    "TCGA-LUAD": ["TP53", "KRAS", "EGFR", "STK11", "KEAP1", "NF1", "BRAF", "ALK"],
    "TCGA-LUSC": ["TP53", "CDKN2A", "KMT2D", "NFE2L2", "FAT1", "PIK3CA", "SOX2", "NOTCH1"],
}

DRIVER_GENES = [
    "TP53",
    "KRAS",
    "KEAP1",
    "STK11",
    "EGFR",
    "NFE2L2",
    "PIK3CA",
    "CDKN2A",
    "FAT1",
    "KMT2D",
    "KMT2C",
    "NF1",
    "BRAF",
    "SMARCA4",
    "PTEN",
    "NOTCH1",
    "NOTCH2",
    "MET",
    "ERBB2",
    "ALK",
    "ROS1",
    "RET",
    "NTRK1",
    "NTRK2",
    "NTRK3",
    "SOX2",
    "TP63",
    "FGFR1",
    "DDR2",
    "CUL3",
]

STAGE_ORDER = {
    "Stage I": 1,
    "Stage IA": 1,
    "Stage IB": 1,
    "Stage II": 2,
    "Stage IIA": 2,
    "Stage IIB": 2,
    "Stage III": 3,
    "Stage IIIA": 3,
    "Stage IIIB": 3,
    "Stage IV": 4,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def smoking_group(status: str | None) -> str | None:
    val = (status or "").strip().lower()
    if not val:
        return None
    if val == "lifelong non-smoker":
        return "non_smoker"
    if "smoker" in val or "reformed smoker" in val:
        return "smoker"
    return None


def stage_bucket(stage: str | None) -> str:
    stage = (stage or "").strip()
    if not stage:
        return "missing"
    for key in ("Stage IV", "Stage IIIB", "Stage IIIA", "Stage III", "Stage IIB", "Stage IIA", "Stage II", "Stage IB", "Stage IA", "Stage I"):
        if key in stage:
            return key.split()[0] + (" " + key.split()[1] if len(key.split()) > 1 else "")
    return "other"


def simplified_stage(stage: str | None) -> str:
    stage = (stage or "").strip()
    if not stage:
        return "missing"
    if "Stage IV" in stage:
        return "IV"
    if "Stage III" in stage:
        return "III"
    if "Stage II" in stage:
        return "II"
    if "Stage I" in stage:
        return "I"
    return "other"


def race_bucket(race: str | None) -> str:
    race = (race or "").strip().lower()
    if not race:
        return "missing"
    if race == "white":
        return "white"
    if race == "black or african american":
        return "black"
    if race == "asian":
        return "asian"
    return "other"


def yes_no(value: str | None) -> str:
    val = (value or "").strip().lower()
    if not val:
        return "missing"
    return "yes" if "yes" in val else "no"


def build_mutation_index(mutations: list[dict[str, str]]) -> dict[str, set[str]]:
    by_case: dict[str, set[str]] = defaultdict(set)
    for row in mutations:
        case_id = row.get("case_id")
        gene = row.get("gene")
        if case_id and gene:
            by_case[case_id].add(gene)
    return by_case


def eligible_patients(
    patients: list[dict[str, str]],
    mutations_by_case: dict[str, set[str]],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in patients:
        if row.get("project_id") not in PROJECTS:
            continue
        if int(float(row.get("mutation_file_count") or 0)) <= 0:
            continue
        if int(float(row.get("expression_file_count") or 0)) <= 0:
            continue
        if smoking_group(row.get("tobacco_smoking_status")) is None:
            continue
        if row["case_id"] not in mutations_by_case:
            continue
        out.append(row)
    return out


def feature_vector(
    row: dict[str, str],
    mutations_by_case: dict[str, set[str]],
    *,
    age_mean: float,
    age_std: float,
) -> list[float]:
    case_id = row["case_id"]
    genes = mutations_by_case.get(case_id, set())
    age = to_float(row.get("age_at_diagnosis_years"))
    age_norm = 0.0 if age is None or age_std <= 0 else (age - age_mean) / age_std

    vec: list[float] = [
        age_norm,
        1.0 if row.get("sex") == "female" else 0.0,
        1.0 if row.get("vital_status") == "Dead" else 0.0,
        1.0 if to_float(row.get("survival_event") or 0) >= 1 else 0.0,
        1.0 if yes_no(row.get("progression_or_recurrence")) == "yes" else 0.0,
        1.0 if yes_no(row.get("prior_treatment")) == "yes" else 0.0,
        1.0 if (row.get("treatment_types") or "").strip() else 0.0,
    ]
    for gene in DRIVER_GENES:
        vec.append(1.0 if gene in genes else 0.0)

    stage = simplified_stage(row.get("ajcc_pathologic_stage"))
    for bucket in ("I", "II", "III", "IV", "other", "missing"):
        vec.append(1.0 if stage == bucket else 0.0)

    race = race_bucket(row.get("race"))
    for bucket in ("white", "black", "asian", "other", "missing"):
        vec.append(1.0 if race == bucket else 0.0)
    return vec


def euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def cohort_centroid(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    return [statistics.mean(v[i] for v in vectors) for i in range(dim)]


def distribution_distance(patient_vec: list[float], centroid: list[float]) -> float:
    return euclidean(patient_vec, centroid)


def select_diverse_patients(
    pool: list[dict[str, str]],
    mutations_by_case: dict[str, set[str]],
    *,
    k: int,
    age_mean: float,
    age_std: float,
    key_drivers: list[str],
) -> list[dict[str, str]]:
    if len(pool) <= k:
        return pool[:k]

    vectors = {
        row["case_id"]: feature_vector(row, mutations_by_case, age_mean=age_mean, age_std=age_std)
        for row in pool
    }
    centroid = cohort_centroid(list(vectors.values()))
    covered_genes: set[str] = set()

    # Seed with the patient closest to the stratum centroid (most typical overall).
    seed = min(pool, key=lambda row: distribution_distance(vectors[row["case_id"]], centroid))
    selected = [seed]
    covered_genes.update(mutations_by_case.get(seed["case_id"], set()))
    remaining = [row for row in pool if row["case_id"] != seed["case_id"]]

    while len(selected) < k and remaining:
        best_row = None
        best_score = -1.0
        for candidate in remaining:
            cand_vec = vectors[candidate["case_id"]]
            cand_genes = mutations_by_case.get(candidate["case_id"], set())
            min_dist = min(euclidean(cand_vec, vectors[s["case_id"]]) for s in selected)
            typicality = 1.0 / (1.0 + distribution_distance(cand_vec, centroid))
            new_key_drivers = sum(
                1 for gene in key_drivers if gene in cand_genes and gene not in covered_genes
            )
            score = min_dist + 0.35 * typicality + 0.8 * new_key_drivers
            if score > best_score:
                best_score = score
                best_row = candidate
        if best_row is None:
            break
        selected.append(best_row)
        covered_genes.update(mutations_by_case.get(best_row["case_id"], set()))
        remaining = [row for row in remaining if row["case_id"] != best_row["case_id"]]
    return selected


def summarize_patient(
    row: dict[str, str],
    mutations_by_case: dict[str, set[str]],
    *,
    selection_rank: int,
    stratum: str,
) -> dict[str, Any]:
    genes = sorted(mutations_by_case.get(row["case_id"], set()))
    return {
        "selection_rank": selection_rank,
        "stratum": stratum,
        "case_submitter_id": row.get("case_submitter_id"),
        "case_id": row.get("case_id"),
        "project_id": row.get("project_id"),
        "smoking_group": smoking_group(row.get("tobacco_smoking_status")),
        "tobacco_smoking_status": row.get("tobacco_smoking_status"),
        "sex": row.get("sex"),
        "race": row.get("race") or "missing",
        "ethnicity": row.get("ethnicity") or "missing",
        "age_at_diagnosis_years": to_float(row.get("age_at_diagnosis_years")),
        "ajcc_pathologic_stage": row.get("ajcc_pathologic_stage") or "missing",
        "vital_status": row.get("vital_status"),
        "survival_time_days": to_float(row.get("survival_time_days")),
        "survival_event": to_float(row.get("survival_event")),
        "progression_or_recurrence": row.get("progression_or_recurrence") or "missing",
        "prior_treatment": row.get("prior_treatment") or "missing",
        "treatment_types": row.get("treatment_types") or "missing",
        "therapeutic_agents": row.get("therapeutic_agents") or "missing",
        "disease_response": row.get("disease_response") or "missing",
        "important_gene_mutations": genes,
        "mutation_count_important_genes": len(genes),
        "slide_count": int(float(row.get("slide_count") or 0)),
        "has_mutation_file": int(float(row.get("mutation_file_count") or 0)) > 0,
        "has_expression_file": int(float(row.get("expression_file_count") or 0)) > 0,
    }


def compare_selected_to_cohort(
    selected: list[dict[str, Any]],
    cohort: list[dict[str, str]],
    mutations_by_case: dict[str, set[str]],
) -> dict[str, Any]:
    def pct(counter: Counter[str], key: str) -> float:
        total = sum(counter.values()) or 1
        return round(100 * counter.get(key, 0) / total, 1)

    def summarize_group(rows: list[dict[str, str]]) -> dict[str, Any]:
        ages = [to_float(r.get("age_at_diagnosis_years")) for r in rows]
        ages = [a for a in ages if a is not None]
        stage = Counter(simplified_stage(r.get("ajcc_pathologic_stage")) for r in rows)
        sex = Counter(r.get("sex") or "missing" for r in rows)
        vital = Counter(r.get("vital_status") or "missing" for r in rows)
        gene_counts = Counter()
        for row in rows:
            for gene in mutations_by_case.get(row["case_id"], set()):
                gene_counts[gene] += 1
        return {
            "n": len(rows),
            "median_age": round(statistics.median(ages), 1) if ages else None,
            "female_pct": pct(sex, "female"),
            "dead_pct": pct(vital, "Dead"),
            "stage_I_pct": pct(stage, "I"),
            "stage_II_pct": pct(stage, "II"),
            "stage_III_pct": pct(stage, "III"),
            "stage_IV_pct": pct(stage, "IV"),
            "top_mutations": dict(gene_counts.most_common(8)),
        }

    out: dict[str, Any] = {}
    for project in PROJECTS:
        cohort_proj = [r for r in cohort if r.get("project_id") == project]
        selected_proj = [r for r in selected if r.get("project_id") == project]
        out[project] = {
            "cohort": summarize_group(cohort_proj),
            "selected": summarize_group(
                [next(row for row in cohort if row["case_id"] == s["case_id"]) for s in selected_proj]
            ),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    data_dir = Path(__file__).resolve().parent
    repo_root = data_dir.parent.parent
    parser.add_argument("--data-dir", type=Path, default=data_dir)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=repo_root / "demo",
    )
    args = parser.parse_args()

    patients = read_csv(args.data_dir / "patient_metadata.tcga_lung.csv")
    mutations = read_csv(args.data_dir / "important_lung_genes" / "important_mutations.tcga_lung.csv")
    mutations_by_case = build_mutation_index(mutations)
    eligible = eligible_patients(patients, mutations_by_case)

    ages = [to_float(r.get("age_at_diagnosis_years")) for r in eligible]
    ages = [a for a in ages if a is not None]
    age_mean = statistics.mean(ages)
    age_std = statistics.pstdev(ages) if len(ages) > 1 else 1.0

    selected_rows: list[dict[str, str]] = []
    selection_notes: list[dict[str, Any]] = []
    for project in PROJECTS:
        for smoking in ("smoker", "non_smoker"):
            pool = [
                row
                for row in eligible
                if row.get("project_id") == project and smoking_group(row.get("tobacco_smoking_status")) == smoking
            ]
            picked = select_diverse_patients(
                pool,
                mutations_by_case,
                k=5,
                age_mean=age_mean,
                age_std=age_std,
                key_drivers=KEY_DRIVERS[project],
            )
            if len(picked) < 5:
                raise SystemExit(
                    f"Insufficient patients for {project} {smoking}: found {len(picked)} eligible, need 5"
                )
            selected_rows.extend(picked)
            selection_notes.append(
                {
                    "project_id": project,
                    "smoking_group": smoking,
                    "eligible_pool_size": len(pool),
                    "selected_case_submitter_ids": [r["case_submitter_id"] for r in picked],
                }
            )

    selected_rows = sorted(
        selected_rows,
        key=lambda r: (r["project_id"], smoking_group(r.get("tobacco_smoking_status")), r["case_submitter_id"]),
    )

    summaries: list[dict[str, Any]] = []
    for idx, row in enumerate(selected_rows, start=1):
        stratum = f"{row['project_id']}|{smoking_group(row.get('tobacco_smoking_status'))}"
        summaries.append(
            summarize_patient(row, mutations_by_case, selection_rank=idx, stratum=stratum)
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "selection_rank",
        "stratum",
        "case_submitter_id",
        "case_id",
        "project_id",
        "smoking_group",
        "tobacco_smoking_status",
        "sex",
        "race",
        "ethnicity",
        "age_at_diagnosis_years",
        "ajcc_pathologic_stage",
        "vital_status",
        "survival_time_days",
        "survival_event",
        "progression_or_recurrence",
        "prior_treatment",
        "treatment_types",
        "therapeutic_agents",
        "disease_response",
        "important_gene_mutations",
        "mutation_count_important_genes",
        "slide_count",
        "has_mutation_file",
        "has_expression_file",
    ]
    csv_path = args.out_dir / "representative_20_patients.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields)
        writer.writeheader()
        for row in summaries:
            out = dict(row)
            out["important_gene_mutations"] = "; ".join(row["important_gene_mutations"])
            writer.writerow(out)

    payload = {
        "selection_criteria": {
            "total_selected": 20,
            "per_project": 10,
            "per_smoking_group_within_project": 5,
            "smoker_definition": "Current smoker or any reformed-smoker category",
            "non_smoker_definition": "Lifelong non-smoker",
            "eligibility": [
                "Has public mutation MAF file",
                "Has RNA expression file",
                "Non-missing smoking status",
            ],
            "algorithm": (
                "Within each histology x smoking stratum, pick 5 patients using "
                "farthest-point sampling on normalized clinical and driver-mutation "
                "features, seeded by the patient closest to the stratum centroid."
            ),
        },
        "selection_notes": selection_notes,
        "patients": summaries,
        "comparison_to_cohort": compare_selected_to_cohort(summaries, patients, mutations_by_case),
    }
    json_path = args.out_dir / "representative_20_patients.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(json.dumps(payload["comparison_to_cohort"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
