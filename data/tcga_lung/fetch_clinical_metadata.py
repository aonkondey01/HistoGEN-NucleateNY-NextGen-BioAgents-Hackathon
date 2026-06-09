#!/usr/bin/env python3
"""Fetch TCGA-LUAD/LUSC clinical metadata from the GDC cases API.

Outputs are written next to this script by default:

    * clinical_metadata.tcga_lung.json          full expanded GDC case records
    * clinical_patient_summary.tcga_lung.tsv   one row per TCGA case/patient
    * clinical_summary.tcga_lung.json          counts for quick inspection

The raw JSON intentionally preserves nested diagnoses, treatments, exposures,
follow-ups, demographic fields, samples, and project metadata so downstream
analyses can recover fields that are not represented in the flattened TSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

GDC_CASES_ENDPOINT = "https://api.gdc.cancer.gov/cases"
LUNG_PROJECTS = ["TCGA-LUAD", "TCGA-LUSC"]
EXPAND = [
    "project",
    "demographic",
    "diagnoses",
    "diagnoses.treatments",
    "exposures",
    "family_histories",
    "follow_ups",
    "samples",
]

SUMMARY_FIELDS = [
    "case_submitter_id",
    "case_id",
    "project_id",
    "disease_type",
    "primary_site",
    "consent_type",
    "index_date",
    "state",
    "has_diagnostic_slide",
    "n_diagnostic_slides",
    "vital_status",
    "days_to_birth",
    "days_to_death",
    "age_at_index",
    "age_is_obfuscated",
    "gender",
    "sex_at_birth",
    "race",
    "ethnicity",
    "year_of_birth",
    "year_of_death",
    "country_of_residence_at_enrollment",
    "primary_diagnosis",
    "diagnosis_is_primary_disease",
    "classification_of_tumor",
    "morphology",
    "icd_10_code",
    "tissue_or_organ_of_origin",
    "site_of_resection_or_biopsy",
    "laterality",
    "tumor_grade",
    "ajcc_pathologic_stage",
    "ajcc_pathologic_t",
    "ajcc_pathologic_n",
    "ajcc_pathologic_m",
    "ajcc_staging_system_edition",
    "year_of_diagnosis",
    "age_at_diagnosis",
    "days_to_diagnosis",
    "days_to_last_follow_up",
    "days_to_last_known_disease_status",
    "days_to_recurrence",
    "last_known_disease_status",
    "progression_or_recurrence",
    "prior_malignancy",
    "prior_treatment",
    "synchronous_malignancy",
    "residual_disease",
    "treatments",
    "treatment_or_therapy",
    "tobacco_smoking_status",
    "pack_years_smoked",
    "cigarettes_per_day",
    "tobacco_smoking_onset_year",
    "tobacco_smoking_quit_year",
    "alcohol_history",
    "alcohol_intensity",
    "last_follow_up_days",
    "last_follow_up_disease_response",
    "n_diagnoses",
    "n_treatments",
    "n_exposures",
    "n_follow_ups",
    "n_samples",
    "n_slides",
]


def _case_filters(project_ids: list[str]) -> dict[str, Any]:
    return {
        "op": "in",
        "content": {
            "field": "project.project_id",
            "value": project_ids,
        },
    }


def _get_json(params: dict[str, Any], *, retries: int = 4) -> dict[str, Any]:
    """GET a GDC JSON response with retry/backoff for transient failures."""
    query_params = {
        key: json.dumps(value) if isinstance(value, (dict, list)) else value
        for key, value in params.items()
    }
    url = f"{GDC_CASES_ENDPOINT}?{urllib.parse.urlencode(query_params)}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as err:
            last_err = err
            wait = 4 * (2**attempt)
            print(
                f"  [retry {attempt + 1}/{retries}] GDC request failed: {err}; "
                f"waiting {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError(f"GDC request failed after {retries} attempts: {last_err}")


def fetch_cases(project_ids: list[str], *, page_size: int = 500) -> list[dict[str, Any]]:
    """Fetch all expanded case records for the requested TCGA projects."""
    cases: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None
    while total is None or offset < total:
        payload = {
            "filters": _case_filters(project_ids),
            "format": "JSON",
            "expand": ",".join(EXPAND),
            "size": page_size,
            "from": offset,
            "sort": "submitter_id:asc",
        }
        result = _get_json(payload)
        data = result["data"]
        hits = data["hits"]
        pagination = data["pagination"]
        total = pagination["total"]
        cases.extend(hits)
        offset += len(hits)
        print(f"  fetched {len(cases)}/{total} cases")
        if not hits:
            break
    cases.sort(key=lambda c: (project_id(c), c.get("submitter_id") or ""))
    return cases


def project_id(case: dict[str, Any]) -> str | None:
    project = case.get("project") or {}
    return project.get("project_id")


def _first(values: list[dict[str, Any]] | None) -> dict[str, Any]:
    return values[0] if values else {}


def _primary_diagnosis(case: dict[str, Any]) -> dict[str, Any]:
    diagnoses = case.get("diagnoses") or []
    for diagnosis in diagnoses:
        if diagnosis.get("diagnosis_is_primary_disease") is True:
            return diagnosis
    return _first(diagnoses)


def _latest_follow_up(case: dict[str, Any]) -> dict[str, Any]:
    follow_ups = case.get("follow_ups") or []
    dated = [f for f in follow_ups if f.get("days_to_follow_up") is not None]
    if dated:
        return max(dated, key=lambda f: f.get("days_to_follow_up") or -1)
    return _first(follow_ups)


def _join_unique(values: list[Any]) -> str:
    cleaned = sorted({str(v) for v in values if v not in (None, "")})
    return "|".join(cleaned)


def load_slide_patient_counts(out_dir: Path) -> Counter[str]:
    """Return diagnostic-slide counts by TCGA case submitter ID, if available."""
    path = out_dir / "slides_metadata.tcga_lung.json"
    if not path.exists():
        return Counter()
    records = json.loads(path.read_text())
    return Counter(
        record["case_submitter_id"]
        for record in records
        if record.get("case_submitter_id")
    )


def flatten_case(case: dict[str, Any], slide_counts: Counter[str]) -> dict[str, Any]:
    demographic = case.get("demographic") or {}
    diagnosis = _primary_diagnosis(case)
    exposure = _first(case.get("exposures") or [])
    latest_follow_up = _latest_follow_up(case)
    treatments = [
        treatment
        for item in case.get("diagnoses") or []
        for treatment in item.get("treatments") or []
    ]
    treatment_types = _join_unique(t.get("treatment_type") for t in treatments)
    treatment_or_therapy = _join_unique(t.get("treatment_or_therapy") for t in treatments)
    submitter_id = case.get("submitter_id")
    n_diagnostic_slides = slide_counts.get(submitter_id, 0)

    row = {
        "case_submitter_id": submitter_id,
        "case_id": case.get("case_id"),
        "project_id": project_id(case),
        "disease_type": case.get("disease_type"),
        "primary_site": case.get("primary_site"),
        "consent_type": case.get("consent_type"),
        "index_date": case.get("index_date"),
        "state": case.get("state"),
        "has_diagnostic_slide": bool(n_diagnostic_slides),
        "n_diagnostic_slides": n_diagnostic_slides,
        "vital_status": demographic.get("vital_status"),
        "days_to_birth": demographic.get("days_to_birth"),
        "days_to_death": demographic.get("days_to_death"),
        "age_at_index": demographic.get("age_at_index"),
        "age_is_obfuscated": demographic.get("age_is_obfuscated"),
        "gender": demographic.get("gender"),
        "sex_at_birth": demographic.get("sex_at_birth"),
        "race": demographic.get("race"),
        "ethnicity": demographic.get("ethnicity"),
        "year_of_birth": demographic.get("year_of_birth"),
        "year_of_death": demographic.get("year_of_death"),
        "country_of_residence_at_enrollment": demographic.get("country_of_residence_at_enrollment"),
        "treatments": treatment_types,
        "treatment_or_therapy": treatment_or_therapy,
        "tobacco_smoking_status": exposure.get("tobacco_smoking_status"),
        "pack_years_smoked": exposure.get("pack_years_smoked"),
        "cigarettes_per_day": exposure.get("cigarettes_per_day"),
        "tobacco_smoking_onset_year": exposure.get("tobacco_smoking_onset_year"),
        "tobacco_smoking_quit_year": exposure.get("tobacco_smoking_quit_year"),
        "alcohol_history": exposure.get("alcohol_history"),
        "alcohol_intensity": exposure.get("alcohol_intensity"),
        "last_follow_up_days": latest_follow_up.get("days_to_follow_up"),
        "last_follow_up_disease_response": latest_follow_up.get("disease_response"),
        "n_diagnoses": len(case.get("diagnoses") or []),
        "n_treatments": len(treatments),
        "n_exposures": len(case.get("exposures") or []),
        "n_follow_ups": len(case.get("follow_ups") or []),
        "n_samples": len(case.get("samples") or []),
        "n_slides": len(case.get("slide_ids") or []),
    }
    for field in SUMMARY_FIELDS:
        row.setdefault(field, diagnosis.get(field))
    return row


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS, extrasaction="ignore", delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def counter_dict(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(v) for v in values if v not in (None, "")).items()))


def build_summary(cases: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    cases_per_project = Counter(row["project_id"] for row in rows)
    return {
        "projects": LUNG_PROJECTS,
        "source": GDC_CASES_ENDPOINT,
        "filters": _case_filters(LUNG_PROJECTS),
        "expanded_relationships": EXPAND,
        "total_cases": len(cases),
        "cases_per_project": dict(sorted(cases_per_project.items())),
        "cases_with_diagnostic_slides": sum(1 for row in rows if row["has_diagnostic_slide"]),
        "vital_status": counter_dict([row["vital_status"] for row in rows]),
        "gender": counter_dict([row["gender"] for row in rows]),
        "race": counter_dict([row["race"] for row in rows]),
        "ethnicity": counter_dict([row["ethnicity"] for row in rows]),
        "primary_diagnosis": counter_dict([row["primary_diagnosis"] for row in rows]),
        "generated_unix": int(time.time()),
        "outputs": {
            "raw_json": "clinical_metadata.tcga_lung.json",
            "patient_summary_tsv": "clinical_patient_summary.tcga_lung.tsv",
            "summary_json": "clinical_summary.tcga_lung.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory to write clinical metadata files (default: script directory)",
    )
    args = parser.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Querying GDC for TCGA lung clinical case metadata ...")
    cases = fetch_cases(LUNG_PROJECTS)

    raw_path = out_dir / "clinical_metadata.tcga_lung.json"
    raw_path.write_text(json.dumps(cases, indent=2, sort_keys=True))

    slide_counts = load_slide_patient_counts(out_dir)
    rows = [flatten_case(case, slide_counts) for case in cases]
    tsv_path = out_dir / "clinical_patient_summary.tcga_lung.tsv"
    write_tsv(tsv_path, rows)

    summary = build_summary(cases, rows)
    summary_path = out_dir / "clinical_summary.tcga_lung.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))

    print("\nSummary")
    print("-------")
    print(f"  total cases                  : {summary['total_cases']}")
    for project, count in summary["cases_per_project"].items():
        print(f"  {project:<27}: {count}")
    print(f"  cases with diagnostic slides : {summary['cases_with_diagnostic_slides']}")
    print(f"  raw JSON                     : {raw_path.name}")
    print(f"  patient summary TSV          : {tsv_path.name}")
    print(f"  clinical summary JSON        : {summary_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
