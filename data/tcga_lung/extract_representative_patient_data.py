#!/usr/bin/env python3
"""Build a complete TCGA data package for the 20 representative lung patients.

Outputs clinical metadata, genome-wide RNA expression, full RPPA proteomics,
somatic mutation calls, molecular file indexes, and per-patient bundles.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import shutil
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from extract_important_lung_genes import (
    GDC_DATA_ENDPOINT,
    _case_parts,
    _download_text,
    fetch_protein_file_index,
    load_molecular_index,
    write_csv,
    write_json,
)

DATA_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATA_DIR.parent.parent

CLINICAL_FIELDS = [
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

RNA_FIELDS = [
    "project_id",
    "case_submitter_id",
    "case_id",
    "sample_submitter_ids",
    "sample_types",
    "aliquot_submitter_ids",
    "file_id",
    "file_name",
    "gene",
    "gene_id",
    "gene_type",
    "unstranded_count",
    "stranded_first_count",
    "stranded_second_count",
    "tpm_unstranded",
    "fpkm_unstranded",
    "fpkm_uq_unstranded",
]

MUTATION_FIELDS = [
    "project_id",
    "case_submitter_id",
    "case_id",
    "sample_submitter_ids",
    "sample_types",
    "file_id",
    "file_name",
    "gene",
    "entrez_gene_id",
    "center",
    "ncbi_build",
    "chromosome",
    "start_position",
    "end_position",
    "strand",
    "variant_classification",
    "variant_type",
    "reference_allele",
    "tumor_seq_allele1",
    "tumor_seq_allele2",
    "dbsnp_rs",
    "tumor_sample_barcode",
    "matched_norm_sample_barcode",
    "hgvsc",
    "hgvsp",
    "hgvsp_short",
    "transcript_id",
    "exon_number",
    "t_depth",
    "t_ref_count",
    "t_alt_count",
    "n_depth",
    "n_ref_count",
    "n_alt_count",
    "filter",
]

RPPA_FIELDS = [
    "project_id",
    "case_submitter_id",
    "case_id",
    "sample_submitter_ids",
    "sample_types",
    "aliquot_submitter_ids",
    "file_id",
    "file_name",
    "peptide_target",
    "agid",
    "lab_id",
    "catalog_number",
    "set_id",
    "protein_expression",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def load_representative_patients(path: Path) -> list[dict[str, str]]:
    return read_csv(path)


def filter_rows(rows: list[dict[str, Any]], case_ids: set[str], key: str = "case_id") -> list[dict[str, Any]]:
    return [row for row in rows if row.get(key) in case_ids]


def extract_full_rna(file_row: dict[str, Any]) -> list[dict[str, Any]]:
    url = file_row.get("download_url") or f"{GDC_DATA_ENDPOINT}/{file_row['file_id']}"
    rows: list[dict[str, Any]] = []
    parts = _case_parts(file_row)
    with _download_text(url) as fh:
        reader: csv.DictReader[str] | None = None
        for line in fh:
            if line.startswith("#"):
                continue
            reader = csv.DictReader(io.StringIO(line + fh.read()), delimiter="\t")
            break
        if reader is None:
            return rows
        for record in reader:
            gene = record.get("gene_name")
            if not gene:
                continue
            rows.append(
                {
                    **parts,
                    "file_id": file_row.get("file_id"),
                    "file_name": file_row.get("file_name"),
                    "gene": gene,
                    "gene_id": record.get("gene_id"),
                    "gene_type": record.get("gene_type"),
                    "unstranded_count": record.get("unstranded"),
                    "stranded_first_count": record.get("stranded_first"),
                    "stranded_second_count": record.get("stranded_second"),
                    "tpm_unstranded": record.get("tpm_unstranded"),
                    "fpkm_unstranded": record.get("fpkm_unstranded"),
                    "fpkm_uq_unstranded": record.get("fpkm_uq_unstranded"),
                }
            )
    return rows


def extract_full_maf(file_row: dict[str, Any]) -> list[dict[str, Any]]:
    url = file_row.get("download_url") or f"{GDC_DATA_ENDPOINT}/{file_row['file_id']}"
    with _download_text(url, gzip_file=True) as fh:
        header: list[str] | None = None
        data_lines: list[str] = []
        for line in fh:
            if line.startswith("#"):
                continue
            if header is None:
                header = line.rstrip("\n").split("\t")
                continue
            data_lines.append(line)
    if header is None:
        return []

    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(data_lines, fieldnames=header, delimiter="\t")
    parts = _case_parts(file_row)
    for record in reader:
        gene = record.get("Hugo_Symbol")
        if not gene:
            continue
        rows.append(
            {
                **parts,
                "file_id": file_row.get("file_id"),
                "file_name": file_row.get("file_name"),
                "gene": gene,
                "entrez_gene_id": record.get("Entrez_Gene_Id"),
                "center": record.get("Center"),
                "ncbi_build": record.get("NCBI_Build"),
                "chromosome": record.get("Chromosome"),
                "start_position": record.get("Start_Position"),
                "end_position": record.get("End_Position"),
                "strand": record.get("Strand"),
                "variant_classification": record.get("Variant_Classification"),
                "variant_type": record.get("Variant_Type"),
                "reference_allele": record.get("Reference_Allele"),
                "tumor_seq_allele1": record.get("Tumor_Seq_Allele1"),
                "tumor_seq_allele2": record.get("Tumor_Seq_Allele2"),
                "dbsnp_rs": record.get("dbSNP_RS"),
                "tumor_sample_barcode": record.get("Tumor_Sample_Barcode"),
                "matched_norm_sample_barcode": record.get("Matched_Norm_Sample_Barcode"),
                "hgvsc": record.get("HGVSc"),
                "hgvsp": record.get("HGVSp"),
                "hgvsp_short": record.get("HGVSp_Short"),
                "transcript_id": record.get("Transcript_ID"),
                "exon_number": record.get("Exon_Number"),
                "t_depth": record.get("t_depth"),
                "t_ref_count": record.get("t_ref_count"),
                "t_alt_count": record.get("t_alt_count"),
                "n_depth": record.get("n_depth"),
                "n_ref_count": record.get("n_ref_count"),
                "n_alt_count": record.get("n_alt_count"),
                "filter": record.get("FILTER"),
            }
        )
    return rows


def extract_full_rppa(file_row: dict[str, Any]) -> list[dict[str, Any]]:
    url = file_row.get("download_url") or f"{GDC_DATA_ENDPOINT}/{file_row['file_id']}"
    rows: list[dict[str, Any]] = []
    parts = _case_parts(file_row)
    with _download_text(url) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            target = record.get("peptide_target")
            if not target:
                continue
            rows.append(
                {
                    **parts,
                    "file_id": file_row.get("file_id"),
                    "file_name": file_row.get("file_name"),
                    "peptide_target": target,
                    "agid": record.get("AGID"),
                    "lab_id": record.get("lab_id"),
                    "catalog_number": record.get("catalog_number"),
                    "set_id": record.get("set_id"),
                    "protein_expression": record.get("protein_expression"),
                }
            )
    return rows


def run_parallel(label: str, files: list[dict[str, Any]], worker, workers: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, row): row for row in files}
        for fut in as_completed(futures):
            file_row = futures[fut]
            done += 1
            try:
                rows.extend(fut.result())
            except Exception as err:
                raise RuntimeError(f"{label} extraction failed for {file_row.get('file_name')}: {err}") from err
            print(f"  {label}: processed {done}/{len(files)} files, rows={len(rows)}")
    return rows


def save_per_patient_bundle(
    out_dir: Path,
    patient: dict[str, str],
    *,
    clinical_json: dict[str, Any],
    mutation_rows: list[dict[str, Any]],
    rna_rows: list[dict[str, Any]],
    rppa_rows: list[dict[str, Any]],
    molecular_files: list[dict[str, Any]],
    slide_rows: list[dict[str, Any]],
) -> None:
    case_id = patient["case_id"]
    bundle_dir = out_dir / "per_patient" / patient["case_submitter_id"]
    bundle_dir.mkdir(parents=True, exist_ok=True)

    write_json(bundle_dir / "clinical.json", clinical_json)
    write_csv(bundle_dir / "somatic_mutations.csv", mutation_rows, MUTATION_FIELDS)
    write_csv(bundle_dir / "genome_wide_gene_expression.csv", rna_rows, RNA_FIELDS)
    write_csv(bundle_dir / "rppa_protein_expression.csv", rppa_rows, RPPA_FIELDS)
    write_csv(bundle_dir / "molecular_file_index.csv", molecular_files, list(molecular_files[0].keys()) if molecular_files else [])
    write_csv(bundle_dir / "slide_metadata.csv", slide_rows, list(slide_rows[0].keys()) if slide_rows else [])

    manifest = {
        "case_submitter_id": patient["case_submitter_id"],
        "case_id": case_id,
        "project_id": patient["project_id"],
        "mutation_rows": len(mutation_rows),
        "rna_rows": len(rna_rows),
        "rppa_rows": len(rppa_rows),
        "slide_count": len(slide_rows),
        "molecular_file_count": len(molecular_files),
    }
    write_json(bundle_dir / "bundle_summary.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--representative-csv",
        type=Path,
        default=REPO_ROOT / "demo" / "representative_20_patients.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "demo" / "data_package",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip-download", action="store_true", help="Only filter local tables; skip GDC downloads.")
    args = parser.parse_args()

    patients = load_representative_patients(args.representative_csv)
    case_ids = {p["case_id"] for p in patients}
    submitter_ids = {p["case_submitter_id"] for p in patients}
    patient_by_case = {p["case_id"]: p for p in patients}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    clinical_dir = args.out_dir / "clinical"
    clinical_dir.mkdir(parents=True, exist_ok=True)

    # Clinical flat + nested JSON from existing extraction.
    all_clinical_csv = read_csv(DATA_DIR / "patient_metadata.tcga_lung.csv")
    clinical_rows = [row for row in all_clinical_csv if row["case_id"] in case_ids]
    clinical_rows.sort(key=lambda r: (r["project_id"], r["case_submitter_id"]))
    write_csv(clinical_dir / "clinical_metadata.csv", clinical_rows, CLINICAL_FIELDS)

    all_clinical_json = json.loads((DATA_DIR / "patient_metadata.tcga_lung.json").read_text())
    clinical_json_rows = [row for row in all_clinical_json if row.get("case_id") in case_ids]
    clinical_json_rows.sort(key=lambda r: (r.get("project_id", ""), r.get("case_submitter_id", "")))
    write_json(clinical_dir / "clinical_metadata.json", clinical_json_rows)
    clinical_by_case = {row["case_id"]: row for row in clinical_json_rows}

    # Slide metadata for WSI linkage.
    slides = json.loads((DATA_DIR / "slides_metadata.tcga_lung.json").read_text())
    slide_rows = [row for row in slides if row.get("case_submitter_id") in submitter_ids]
    write_json(args.out_dir / "slide_metadata.json", slide_rows)
    slides_by_submitter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in slide_rows:
        slides_by_submitter[row["case_submitter_id"]].append(row)

    # Filter important-gene tables already extracted for the full cohort.
    important_dir = DATA_DIR / "important_lung_genes"
    imp_mut = filter_rows(read_csv(important_dir / "important_mutations.tcga_lung.csv"), case_ids)
    imp_rna = filter_rows(read_csv(important_dir / "important_gene_expression.tcga_lung.csv"), case_ids)
    imp_rppa = filter_rows(read_csv(important_dir / "important_protein_expression.tcga_lung.csv"), case_ids)
    write_csv(args.out_dir / "important_gene_mutations.csv", imp_mut, list(imp_mut[0].keys()) if imp_mut else [])
    write_csv(args.out_dir / "important_gene_expression.csv", imp_rna, list(imp_rna[0].keys()) if imp_rna else [])
    write_csv(args.out_dir / "important_gene_rppa_protein.csv", imp_rppa, list(imp_rppa[0].keys()) if imp_rppa else [])

    molecular_index = read_csv(DATA_DIR / "molecular_files.tcga_lung.csv")
    rep_molecular = [row for row in molecular_index if row["case_id"] in case_ids]
    write_csv(args.out_dir / "molecular_file_index.csv", rep_molecular, list(rep_molecular[0].keys()) if rep_molecular else [])
    molecular_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rep_molecular:
        molecular_by_case[row["case_id"]].append(row)

    mutation_files = [row for row in rep_molecular if row["molecular_data_kind"] == "mutation"]
    expression_files = [row for row in rep_molecular if row["molecular_data_kind"] == "expression"]

    all_mutation_rows: list[dict[str, Any]] = []
    all_rna_rows: list[dict[str, Any]] = []
    all_rppa_rows: list[dict[str, Any]] = []

    if not args.skip_download:
        print(f"Downloading full somatic mutation tables for {len(mutation_files)} MAF files ...")
        all_mutation_rows = run_parallel("mutation", mutation_files, extract_full_maf, args.workers)
        write_csv(args.out_dir / "somatic_mutations.csv", all_mutation_rows, MUTATION_FIELDS)

        print(f"Downloading genome-wide RNA expression for {len(expression_files)} STAR-count files ...")
        all_rna_rows = run_parallel("rna", expression_files, extract_full_rna, args.workers)
        write_csv(args.out_dir / "genome_wide_gene_expression.csv", all_rna_rows, RNA_FIELDS)

        print("Fetching RPPA file index and downloading full proteomics ...")
        protein_files = [row for row in fetch_protein_file_index(sorted(case_ids)) if row.get("case_id") in case_ids]
        write_json(args.out_dir / "rppa_file_index.json", protein_files)
        write_csv(
            args.out_dir / "rppa_file_index.csv",
            protein_files,
            list(protein_files[0].keys()) if protein_files else [],
        )
        all_rppa_rows = run_parallel("rppa", protein_files, extract_full_rppa, args.workers)
        write_csv(args.out_dir / "rppa_protein_expression.csv", all_rppa_rows, RPPA_FIELDS)
    else:
        print("Skipping GDC downloads (--skip-download).")

    # Per-patient bundles.
    per_patient_dir = args.out_dir / "per_patient"
    if per_patient_dir.exists():
        shutil.rmtree(per_patient_dir)
    per_patient_dir.mkdir(parents=True, exist_ok=True)

    mutations_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rna_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rppa_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_mutation_rows:
        mutations_by_case[row["case_id"]].append(row)
    for row in all_rna_rows:
        rna_by_case[row["case_id"]].append(row)
    for row in all_rppa_rows:
        rppa_by_case[row["case_id"]].append(row)

    for patient in patients:
        case_id = patient["case_id"]
        save_per_patient_bundle(
            args.out_dir,
            patient,
            clinical_json=clinical_by_case.get(case_id, {}),
            mutation_rows=mutations_by_case.get(case_id, []),
            rna_rows=rna_by_case.get(case_id, []),
            rppa_rows=rppa_by_case.get(case_id, []),
            molecular_files=molecular_by_case.get(case_id, []),
            slide_rows=slides_by_submitter.get(patient["case_submitter_id"], []),
        )

    availability = []
    for patient in patients:
        case_id = patient["case_id"]
        sid = patient["case_submitter_id"]
        availability.append(
            {
                "case_submitter_id": sid,
                "case_id": case_id,
                "project_id": patient["project_id"],
                "clinical_fields": len(clinical_by_case.get(case_id, {})),
                "slide_files": len(slides_by_submitter.get(sid, [])),
                "mutation_maf_files": sum(1 for r in rep_molecular if r["case_id"] == case_id and r["molecular_data_kind"] == "mutation"),
                "expression_files": sum(1 for r in rep_molecular if r["case_id"] == case_id and r["molecular_data_kind"] == "expression"),
                "somatic_mutation_rows": len(mutations_by_case.get(case_id, [])),
                "genome_wide_rna_rows": len(rna_by_case.get(case_id, [])),
                "rppa_protein_rows": len(rppa_by_case.get(case_id, [])),
                "important_gene_mutation_rows": sum(1 for r in imp_mut if r["case_id"] == case_id),
                "important_gene_rna_rows": sum(1 for r in imp_rna if r["case_id"] == case_id),
                "important_gene_rppa_rows": sum(1 for r in imp_rppa if r["case_id"] == case_id),
            }
        )
    write_json(args.out_dir / "data_availability_summary.json", availability)
    write_csv(args.out_dir / "data_availability_summary.csv", availability, list(availability[0].keys()) if availability else [])

    summary = {
        "patient_count": len(patients),
        "clinical_records": len(clinical_rows),
        "slide_records": len(slide_rows),
        "molecular_file_records": len(rep_molecular),
        "important_gene_mutation_rows": len(imp_mut),
        "important_gene_rna_rows": len(imp_rna),
        "important_gene_rppa_rows": len(imp_rppa),
        "somatic_mutation_rows": len(all_mutation_rows),
        "genome_wide_rna_rows": len(all_rna_rows),
        "rppa_protein_rows": len(all_rppa_rows),
        "output_directory": str(args.out_dir),
        "notes": [
            "Clinical metadata includes demographics, staging, smoking, survival, and treatment fields extracted from GDC.",
            "Genome-wide RNA expression uses GDC STAR - Counts augmented gene count files.",
            "Proteomics uses TCGA RPPA protein expression tables (all peptide targets).",
            "Somatic mutations use GDC open masked MAF files (SNVs/indels).",
            "Important-gene tables are a focused subset of the 30 lung driver genes used elsewhere in this repo.",
            "Diagnostic H&E slide metadata is included; raw SVS files are not downloaded here.",
        ],
    }
    write_json(args.out_dir / "package_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(DATA_DIR))
    raise SystemExit(main())
