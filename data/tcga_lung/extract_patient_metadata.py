#!/usr/bin/env python3
"""Extract TCGA lung clinical and molecular metadata from the GDC API.

The existing slide metadata in this directory defines the cohort: every unique
case_id in ``slides_metadata.tcga_lung.json``. This script fetches clinical
case data for those patients and indexes open GDC mutation/expression files that
can be downloaded later with the emitted gdc-client manifests.

Outputs written to ``--out-dir``:

* patient_metadata.tcga_lung.csv
* patient_metadata.tcga_lung.json
* molecular_files.tcga_lung.csv
* molecular_files.tcga_lung.json
* gdc_manifest.mutation.tcga_lung.txt
* gdc_manifest.expression.tcga_lung.txt
* patient_metadata_summary.tcga_lung.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GDC_CASES_ENDPOINT = "https://api.gdc.cancer.gov/cases"
GDC_FILES_ENDPOINT = "https://api.gdc.cancer.gov/files"
GDC_DATA_ENDPOINT = "https://api.gdc.cancer.gov/data"

CASE_FIELDS = [
    "case_id",
    "submitter_id",
    "project.project_id",
    "demographic.gender",
    "demographic.race",
    "demographic.ethnicity",
    "demographic.days_to_birth",
    "demographic.year_of_birth",
    "demographic.vital_status",
    "demographic.days_to_death",
    "diagnoses.age_at_diagnosis",
    "diagnoses.days_to_diagnosis",
    "diagnoses.days_to_last_follow_up",
    "diagnoses.days_to_last_known_disease_status",
    "diagnoses.primary_diagnosis",
    "diagnoses.tumor_stage",
    "diagnoses.ajcc_pathologic_stage",
    "diagnoses.ajcc_pathologic_t",
    "diagnoses.ajcc_pathologic_n",
    "diagnoses.ajcc_pathologic_m",
    "diagnoses.prior_malignancy",
    "diagnoses.prior_treatment",
    "diagnoses.synchronous_malignancy",
    "diagnoses.treatments.treatment_type",
    "diagnoses.treatments.treatment_or_therapy",
    "diagnoses.treatments.days_to_treatment_start",
    "diagnoses.treatments.days_to_treatment_end",
    "diagnoses.treatments.therapeutic_agents",
    "diagnoses.treatments.initial_disease_status",
    "diagnoses.treatments.treatment_intent_type",
    "diagnoses.treatments.regimen_or_line_of_therapy",
    "diagnoses.treatments.treatment_outcome",
    "exposures.tobacco_smoking_status",
    "exposures.tobacco_smoking_onset_year",
    "exposures.years_smoked",
    "exposures.pack_years_smoked",
    "exposures.cigarettes_per_day",
    "exposures.alcohol_history",
    "follow_ups.days_to_follow_up",
    "follow_ups.days_to_progression",
    "follow_ups.progression_or_recurrence",
    "follow_ups.disease_response",
]

FILE_FIELDS = [
    "file_id",
    "file_name",
    "md5sum",
    "file_size",
    "state",
    "data_category",
    "data_type",
    "data_format",
    "experimental_strategy",
    "access",
    "analysis.workflow_type",
    "cases.case_id",
    "cases.submitter_id",
    "cases.project.project_id",
    "cases.samples.submitter_id",
    "cases.samples.sample_type",
    "cases.samples.portions.analytes.aliquots.submitter_id",
]

MOLECULAR_DATA_TYPES = {
    "mutation": "Masked Somatic Mutation",
    "expression": "Gene Expression Quantification",
}

PATIENT_CSV_FIELDS = [
    "case_submitter_id",
    "case_id",
    "project_id",
    "slide_count",
    "slide_sample_submitter_ids",
    "slide_sample_types",
    "sex",
    "race",
    "ethnicity",
    "vital_status",
    "days_to_birth",
    "year_of_birth",
    "age_at_diagnosis_days",
    "age_at_diagnosis_years",
    "days_to_death",
    "days_to_last_follow_up",
    "days_to_last_known_disease_status",
    "survival_time_days",
    "survival_event",
    "primary_diagnosis",
    "diagnosis_count",
    "days_to_diagnosis",
    "prior_malignancy",
    "prior_treatment",
    "synchronous_malignancy",
    "ajcc_pathologic_stage",
    "ajcc_pathologic_t",
    "ajcc_pathologic_n",
    "ajcc_pathologic_m",
    "tumor_stage",
    "tobacco_smoking_status",
    "tobacco_smoking_onset_year",
    "years_smoked",
    "pack_years_smoked",
    "cigarettes_per_day",
    "alcohol_history",
    "treatment_types",
    "treatment_or_therapy",
    "therapeutic_agents",
    "initial_disease_status",
    "treatment_intent_types",
    "regimen_or_line_of_therapy",
    "treatment_outcomes",
    "days_to_treatment_start",
    "days_to_treatment_end",
    "follow_up_count",
    "last_follow_up_days",
    "disease_response",
    "progression_or_recurrence",
    "days_to_progression",
    "mutation_file_count",
    "expression_file_count",
]

MOLECULAR_CSV_FIELDS = [
    "molecular_data_kind",
    "case_submitter_id",
    "case_id",
    "project_id",
    "file_id",
    "file_name",
    "md5sum",
    "file_size",
    "state",
    "data_category",
    "data_type",
    "data_format",
    "experimental_strategy",
    "access",
    "workflow_type",
    "sample_submitter_ids",
    "sample_types",
    "tumor_sample_submitter_ids",
    "normal_sample_submitter_ids",
    "aliquot_submitter_ids",
    "download_url",
]


def _post(endpoint: str, payload: dict[str, Any], *, retries: int = 4) -> Any:
    """POST JSON to GDC with simple exponential-backoff retries."""
    data = json.dumps(payload).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8")
            if payload.get("return_type") == "manifest":
                return raw
            return json.loads(raw)
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


def _case_filter(case_ids: list[str]) -> dict[str, Any]:
    return {"op": "in", "content": {"field": "case_id", "value": case_ids}}


def _file_filter(case_ids: list[str], data_type: str) -> dict[str, Any]:
    return {
        "op": "and",
        "content": [
            {"op": "in", "content": {"field": "cases.case_id", "value": case_ids}},
            {"op": "in", "content": {"field": "files.data_type", "value": [data_type]}},
        ],
    }


def _clean(value: Any) -> Any:
    if value in ("", "Not Reported", "not reported", "Unknown", "unknown", "--"):
        return None
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        value = _clean(value)
        if value is None:
            continue
        key = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _join(values: list[Any]) -> str | None:
    cleaned = _unique(values)
    if not cleaned:
        return None
    return "; ".join(str(v) for v in cleaned)


def _first(values: list[Any]) -> Any:
    cleaned = _unique(values)
    return cleaned[0] if cleaned else None


def _numbers(values: list[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        value = _clean(value)
        if value is None:
            continue
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            pass
    return out


def _min_number(values: list[Any]) -> int | float | None:
    nums = _numbers(values)
    if not nums:
        return None
    val = min(nums)
    return int(val) if val.is_integer() else val


def _max_number(values: list[Any]) -> int | float | None:
    nums = _numbers(values)
    if not nums:
        return None
    val = max(nums)
    return int(val) if val.is_integer() else val


def _age_years(age_days: Any) -> float | None:
    try:
        return round(float(age_days) / 365.25, 2)
    except (TypeError, ValueError):
        return None


def read_slide_cohort(path: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    slides = json.loads(path.read_text())
    by_case: dict[str, dict[str, Any]] = {}
    for slide in slides:
        case_id = slide["case_id"]
        entry = by_case.setdefault(
            case_id,
            {
                "case_id": case_id,
                "case_submitter_id": slide["case_submitter_id"],
                "project_id": slide["project_id"],
                "slide_count": 0,
                "slide_sample_submitter_ids": [],
                "slide_sample_types": [],
            },
        )
        entry["slide_count"] += 1
        entry["slide_sample_submitter_ids"].append(slide.get("sample_submitter_id"))
        entry["slide_sample_types"].append(slide.get("sample_type"))

    for entry in by_case.values():
        entry["slide_sample_submitter_ids"] = _join(entry["slide_sample_submitter_ids"])
        entry["slide_sample_types"] = _join(entry["slide_sample_types"])

    case_ids = sorted(by_case)
    return case_ids, by_case


def fetch_cases(case_ids: list[str]) -> list[dict[str, Any]]:
    payload = {
        "filters": _case_filter(case_ids),
        "fields": ",".join(CASE_FIELDS),
        "format": "JSON",
        "size": 100000,
    }
    result = _post(GDC_CASES_ENDPOINT, payload)
    return result["data"]["hits"]


def fetch_file_metadata(case_ids: list[str], kind: str, data_type: str) -> list[dict[str, Any]]:
    payload = {
        "filters": _file_filter(case_ids, data_type),
        "fields": ",".join(FILE_FIELDS),
        "format": "JSON",
        "size": 100000,
    }
    result = _post(GDC_FILES_ENDPOINT, payload)
    return [_flatten_file(hit, kind) for hit in result["data"]["hits"]]


def fetch_manifest(case_ids: list[str], data_type: str) -> str:
    payload = {
        "filters": _file_filter(case_ids, data_type),
        "return_type": "manifest",
        "size": 100000,
    }
    return _post(GDC_FILES_ENDPOINT, payload)


def _flatten_case(case: dict[str, Any], slide_info: dict[str, Any]) -> dict[str, Any]:
    diagnoses = _as_list(case.get("diagnoses"))
    exposures = _as_list(case.get("exposures"))
    treatments: list[dict[str, Any]] = []
    for diagnosis in diagnoses:
        treatments.extend(_as_list(diagnosis.get("treatments")))
    follow_ups = _as_list(case.get("follow_ups"))
    demographic = case.get("demographic") or {}

    age_at_diagnosis = _first([d.get("age_at_diagnosis") for d in diagnoses])
    days_to_death = _clean(demographic.get("days_to_death"))
    days_to_last_follow_up = _max_number(
        [d.get("days_to_last_follow_up") for d in diagnoses]
        + [f.get("days_to_follow_up") for f in follow_ups]
    )
    survival_time = days_to_death if days_to_death is not None else days_to_last_follow_up
    vital_status = _clean(demographic.get("vital_status"))

    flattened = {
        **slide_info,
        "case_submitter_id": case.get("submitter_id") or slide_info["case_submitter_id"],
        "case_id": case.get("case_id") or slide_info["case_id"],
        "project_id": (case.get("project") or {}).get("project_id") or slide_info["project_id"],
        "sex": _clean(demographic.get("gender")),
        "race": _clean(demographic.get("race")),
        "ethnicity": _clean(demographic.get("ethnicity")),
        "vital_status": vital_status,
        "days_to_birth": _clean(demographic.get("days_to_birth")),
        "year_of_birth": _clean(demographic.get("year_of_birth")),
        "age_at_diagnosis_days": age_at_diagnosis,
        "age_at_diagnosis_years": _age_years(age_at_diagnosis),
        "days_to_death": days_to_death,
        "days_to_last_follow_up": days_to_last_follow_up,
        "days_to_last_known_disease_status": _max_number(
            [d.get("days_to_last_known_disease_status") for d in diagnoses]
        ),
        "survival_time_days": survival_time,
        "survival_event": 1 if str(vital_status).lower() == "dead" else 0 if vital_status else None,
        "primary_diagnosis": _join([d.get("primary_diagnosis") for d in diagnoses]),
        "diagnosis_count": len(diagnoses),
        "days_to_diagnosis": _min_number([d.get("days_to_diagnosis") for d in diagnoses]),
        "prior_malignancy": _join([d.get("prior_malignancy") for d in diagnoses]),
        "prior_treatment": _join([d.get("prior_treatment") for d in diagnoses]),
        "synchronous_malignancy": _join([d.get("synchronous_malignancy") for d in diagnoses]),
        "ajcc_pathologic_stage": _join([d.get("ajcc_pathologic_stage") for d in diagnoses]),
        "ajcc_pathologic_t": _join([d.get("ajcc_pathologic_t") for d in diagnoses]),
        "ajcc_pathologic_n": _join([d.get("ajcc_pathologic_n") for d in diagnoses]),
        "ajcc_pathologic_m": _join([d.get("ajcc_pathologic_m") for d in diagnoses]),
        "tumor_stage": _join([d.get("tumor_stage") for d in diagnoses]),
        "tobacco_smoking_status": _join([e.get("tobacco_smoking_status") for e in exposures]),
        "tobacco_smoking_onset_year": _join([e.get("tobacco_smoking_onset_year") for e in exposures]),
        "years_smoked": _max_number([e.get("years_smoked") for e in exposures]),
        "pack_years_smoked": _max_number([e.get("pack_years_smoked") for e in exposures]),
        "cigarettes_per_day": _max_number([e.get("cigarettes_per_day") for e in exposures]),
        "alcohol_history": _join([e.get("alcohol_history") for e in exposures]),
        "treatment_types": _join([t.get("treatment_type") for t in treatments]),
        "treatment_or_therapy": _join([t.get("treatment_or_therapy") for t in treatments]),
        "therapeutic_agents": _join([t.get("therapeutic_agents") for t in treatments]),
        "initial_disease_status": _join([t.get("initial_disease_status") for t in treatments]),
        "treatment_intent_types": _join([t.get("treatment_intent_type") for t in treatments]),
        "regimen_or_line_of_therapy": _join([t.get("regimen_or_line_of_therapy") for t in treatments]),
        "treatment_outcomes": _join([t.get("treatment_outcome") for t in treatments]),
        "days_to_treatment_start": _min_number([t.get("days_to_treatment_start") for t in treatments]),
        "days_to_treatment_end": _max_number([t.get("days_to_treatment_end") for t in treatments]),
        "follow_up_count": len(follow_ups),
        "last_follow_up_days": _max_number([f.get("days_to_follow_up") for f in follow_ups]),
        "disease_response": _join([f.get("disease_response") for f in follow_ups]),
        "progression_or_recurrence": _join([f.get("progression_or_recurrence") for f in follow_ups]),
        "days_to_progression": _min_number([f.get("days_to_progression") for f in follow_ups]),
        "mutation_file_count": 0,
        "expression_file_count": 0,
    }
    return {
        **flattened,
        "diagnoses": diagnoses,
        "exposures": exposures,
        "treatments": treatments,
        "follow_ups": follow_ups,
    }


def _flatten_file(hit: dict[str, Any], kind: str) -> dict[str, Any]:
    case = _as_list(hit.get("cases"))[0] if hit.get("cases") else {}
    samples = _as_list(case.get("samples"))
    sample_submitter_ids = [s.get("submitter_id") for s in samples]
    sample_types = [s.get("sample_type") for s in samples]
    tumor_samples = [
        s.get("submitter_id")
        for s in samples
        if "tumor" in str(s.get("sample_type", "")).lower()
    ]
    normal_samples = [
        s.get("submitter_id")
        for s in samples
        if "normal" in str(s.get("sample_type", "")).lower()
        or "blood" in str(s.get("sample_type", "")).lower()
    ]
    aliquots: list[str] = []
    for sample in samples:
        for portion in _as_list(sample.get("portions")):
            for analyte in _as_list(portion.get("analytes")):
                for aliquot in _as_list(analyte.get("aliquots")):
                    if aliquot.get("submitter_id"):
                        aliquots.append(aliquot["submitter_id"])

    file_id = hit.get("file_id")
    return {
        "molecular_data_kind": kind,
        "case_submitter_id": case.get("submitter_id"),
        "case_id": case.get("case_id"),
        "project_id": (case.get("project") or {}).get("project_id"),
        "file_id": file_id,
        "file_name": hit.get("file_name"),
        "md5sum": hit.get("md5sum"),
        "file_size": hit.get("file_size"),
        "state": hit.get("state"),
        "data_category": hit.get("data_category"),
        "data_type": hit.get("data_type"),
        "data_format": hit.get("data_format"),
        "experimental_strategy": hit.get("experimental_strategy"),
        "access": hit.get("access"),
        "workflow_type": (hit.get("analysis") or {}).get("workflow_type"),
        "sample_submitter_ids": _join(sample_submitter_ids),
        "sample_types": _join(sample_types),
        "tumor_sample_submitter_ids": _join(tumor_samples),
        "normal_sample_submitter_ids": _join(normal_samples),
        "aliquot_submitter_ids": _join(aliquots),
        "download_url": f"{GDC_DATA_ENDPOINT}/{file_id}" if file_id else None,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def build_summary(
    patients: list[dict[str, Any]],
    molecular_files: list[dict[str, Any]],
    manifests: dict[str, str],
) -> dict[str, Any]:
    missing_by_field = {
        field: sum(1 for row in patients if row.get(field) in (None, ""))
        for field in PATIENT_CSV_FIELDS
    }
    molecular_counts = Counter(row["molecular_data_kind"] for row in molecular_files)
    molecular_cases: dict[str, set[str]] = defaultdict(set)
    molecular_bytes: Counter[str] = Counter()
    for row in molecular_files:
        kind = row["molecular_data_kind"]
        if row.get("case_id"):
            molecular_cases[kind].add(row["case_id"])
        molecular_bytes[kind] += int(row.get("file_size") or 0)

    return {
        "generated_unix": int(time.time()),
        "cohort_source": "slides_metadata.tcga_lung.json",
        "patient_count": len(patients),
        "project_counts": dict(Counter(row.get("project_id") for row in patients)),
        "sex_counts": dict(Counter(row.get("sex") or "missing" for row in patients)),
        "race_counts": dict(Counter(row.get("race") or "missing" for row in patients)),
        "ethnicity_counts": dict(Counter(row.get("ethnicity") or "missing" for row in patients)),
        "vital_status_counts": dict(
            Counter(row.get("vital_status") or "missing" for row in patients)
        ),
        "smoking_status_counts": dict(
            Counter(row.get("tobacco_smoking_status") or "missing" for row in patients)
        ),
        "sample_type_counts_from_slides": dict(
            Counter(row.get("slide_sample_types") or "missing" for row in patients)
        ),
        "patients_with_mutation_files": len(molecular_cases.get("mutation", set())),
        "patients_with_expression_files": len(molecular_cases.get("expression", set())),
        "molecular_file_counts": dict(molecular_counts),
        "molecular_total_bytes": dict(molecular_bytes),
        "manifest_records": {
            kind: max(0, len([ln for ln in text.splitlines() if ln.strip()]) - 1)
            for kind, text in manifests.items()
        },
        "missing_patient_field_counts": missing_by_field,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slides-metadata",
        type=Path,
        default=Path(__file__).resolve().parent / "slides_metadata.tcga_lung.json",
        help="Existing slide metadata JSON that defines the patient cohort.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory where extracted metadata files should be written.",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    case_ids, slide_by_case = read_slide_cohort(args.slides_metadata)
    print(f"Slide cohort: {len(case_ids)} unique cases from {args.slides_metadata}")

    print("Fetching clinical case metadata from GDC ...")
    cases = fetch_cases(case_ids)
    cases_by_id = {case["case_id"]: case for case in cases}
    patients: list[dict[str, Any]] = []
    for case_id in case_ids:
        if case_id not in cases_by_id:
            patients.append({**slide_by_case[case_id], "mutation_file_count": 0, "expression_file_count": 0})
            continue
        patients.append(_flatten_case(cases_by_id[case_id], slide_by_case[case_id]))

    print("Fetching molecular file metadata and manifests from GDC ...")
    molecular_files: list[dict[str, Any]] = []
    manifests: dict[str, str] = {}
    for kind, data_type in MOLECULAR_DATA_TYPES.items():
        files = fetch_file_metadata(case_ids, kind, data_type)
        molecular_files.extend(files)
        manifests[kind] = fetch_manifest(case_ids, data_type)
        print(f"  {kind}: {len(files)} files")

    molecular_counts_by_case: dict[str, Counter[str]] = defaultdict(Counter)
    for row in molecular_files:
        if row.get("case_id"):
            molecular_counts_by_case[row["case_id"]][row["molecular_data_kind"]] += 1
    for row in patients:
        counts = molecular_counts_by_case.get(row["case_id"], Counter())
        row["mutation_file_count"] = counts.get("mutation", 0)
        row["expression_file_count"] = counts.get("expression", 0)

    patients.sort(key=lambda row: (row.get("project_id") or "", row.get("case_submitter_id") or ""))
    molecular_files.sort(
        key=lambda row: (
            row.get("molecular_data_kind") or "",
            row.get("project_id") or "",
            row.get("case_submitter_id") or "",
            row.get("file_name") or "",
        )
    )

    write_csv(args.out_dir / "patient_metadata.tcga_lung.csv", patients, PATIENT_CSV_FIELDS)
    write_json(args.out_dir / "patient_metadata.tcga_lung.json", patients)
    write_csv(args.out_dir / "molecular_files.tcga_lung.csv", molecular_files, MOLECULAR_CSV_FIELDS)
    write_json(args.out_dir / "molecular_files.tcga_lung.json", molecular_files)
    for kind, text in manifests.items():
        (args.out_dir / f"gdc_manifest.{kind}.tcga_lung.txt").write_text(text)

    summary = build_summary(patients, molecular_files, manifests)
    write_json(args.out_dir / "patient_metadata_summary.tcga_lung.json", summary)

    print("\nWrote:")
    for name in [
        "patient_metadata.tcga_lung.csv",
        "patient_metadata.tcga_lung.json",
        "molecular_files.tcga_lung.csv",
        "molecular_files.tcga_lung.json",
        "gdc_manifest.mutation.tcga_lung.txt",
        "gdc_manifest.expression.tcga_lung.txt",
        "patient_metadata_summary.tcga_lung.json",
    ]:
        print(f"  {args.out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
