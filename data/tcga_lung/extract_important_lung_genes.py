#!/usr/bin/env python3
"""Extract important LUAD/LUSC gene data from public TCGA/GDC files.

This script uses the slide-defined TCGA lung cohort already captured in this
directory and extracts a focused, public dataset for commonly important lung
adenocarcinoma and lung squamous cell carcinoma genes:

* masked somatic mutation calls from MAF files,
* RNA-seq STAR gene-count expression rows, and
* Reverse Phase Protein Array (RPPA) protein-expression rows where TCGA has a
  matching antibody target.

Raw genome-wide molecular files are streamed from GDC and are not stored. Only
the disease-focused tables are written.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

GDC_FILES_ENDPOINT = "https://api.gdc.cancer.gov/files"
GDC_DATA_ENDPOINT = "https://api.gdc.cancer.gov/data"

IMPORTANT_GENES: dict[str, dict[str, str]] = {
    # Lung adenocarcinoma drivers and recurrent tumor suppressors.
    "EGFR": {
        "disease_context": "LUAD",
        "category": "targetable_driver",
        "notes": "Activating EGFR mutations are clinically actionable in LUAD.",
    },
    "KRAS": {
        "disease_context": "LUAD",
        "category": "targetable_driver",
        "notes": "Common LUAD driver; KRAS G12C is clinically actionable.",
    },
    "ALK": {
        "disease_context": "LUAD",
        "category": "targetable_fusion_driver",
        "notes": "Usually detected as a fusion, not fully captured by MAF SNV/indel calls.",
    },
    "ROS1": {
        "disease_context": "LUAD",
        "category": "targetable_fusion_driver",
        "notes": "Usually detected as a fusion.",
    },
    "RET": {
        "disease_context": "LUAD",
        "category": "targetable_fusion_driver",
        "notes": "Usually detected as a fusion.",
    },
    "NTRK1": {
        "disease_context": "LUAD",
        "category": "targetable_fusion_driver",
        "notes": "Rare targetable fusion gene.",
    },
    "NTRK2": {
        "disease_context": "LUAD",
        "category": "targetable_fusion_driver",
        "notes": "Rare targetable fusion gene.",
    },
    "NTRK3": {
        "disease_context": "LUAD",
        "category": "targetable_fusion_driver",
        "notes": "Rare targetable fusion gene.",
    },
    "BRAF": {
        "disease_context": "LUAD",
        "category": "targetable_driver",
        "notes": "BRAF V600E is clinically actionable.",
    },
    "MET": {
        "disease_context": "LUAD",
        "category": "targetable_driver",
        "notes": "MET exon 14 skipping/amplification can be actionable; MAF may not fully capture exon skipping.",
    },
    "ERBB2": {
        "disease_context": "LUAD",
        "category": "targetable_driver",
        "notes": "HER2/ERBB2 insertions and amplifications can be actionable.",
    },
    "STK11": {
        "disease_context": "LUAD",
        "category": "tumor_suppressor",
        "notes": "Important LUAD co-mutation and immunotherapy-resistance context.",
    },
    "SMARCA4": {
        "disease_context": "LUAD",
        "category": "tumor_suppressor",
        "notes": "Associated with aggressive biology in subsets of LUAD.",
    },
    "NF1": {
        "disease_context": "LUAD",
        "category": "ras_pathway",
        "notes": "RAS pathway alteration.",
    },
    # Shared or LUSC-enriched genes/pathways.
    "TP53": {
        "disease_context": "LUAD,LUSC",
        "category": "tumor_suppressor",
        "notes": "Very common in lung cancer, especially LUSC.",
    },
    "KEAP1": {
        "disease_context": "LUAD,LUSC",
        "category": "oxidative_stress_pathway",
        "notes": "NRF2/oxidative-stress pathway alteration.",
    },
    "NFE2L2": {
        "disease_context": "LUAD,LUSC",
        "category": "oxidative_stress_pathway",
        "notes": "NRF2 transcription factor; recurrent in LUSC.",
    },
    "PIK3CA": {
        "disease_context": "LUAD,LUSC",
        "category": "pi3k_pathway",
        "notes": "PI3K pathway mutation/amplification.",
    },
    "CDKN2A": {
        "disease_context": "LUSC",
        "category": "cell_cycle_tumor_suppressor",
        "notes": "Cell-cycle tumor suppressor loss is common in LUSC.",
    },
    "SOX2": {
        "disease_context": "LUSC",
        "category": "squamous_lineage",
        "notes": "Squamous lineage driver, often amplified.",
    },
    "TP63": {
        "disease_context": "LUSC",
        "category": "squamous_lineage",
        "notes": "Squamous lineage driver, often amplified.",
    },
    "PTEN": {
        "disease_context": "LUSC",
        "category": "pi3k_pathway",
        "notes": "PI3K pathway dysregulation through PTEN loss.",
    },
    "CUL3": {
        "disease_context": "LUSC",
        "category": "oxidative_stress_pathway",
        "notes": "NRF2/KEAP1/CUL3 pathway.",
    },
    "FGFR1": {
        "disease_context": "LUSC",
        "category": "copy_number_driver",
        "notes": "Potential therapeutic relevance, often amplified.",
    },
    "DDR2": {
        "disease_context": "LUSC",
        "category": "kinase",
        "notes": "Less common LUSC kinase alteration.",
    },
    "NOTCH1": {
        "disease_context": "LUSC",
        "category": "squamous_differentiation",
        "notes": "Squamous differentiation/tumor suppressor pathway.",
    },
    "NOTCH2": {
        "disease_context": "LUSC",
        "category": "squamous_differentiation",
        "notes": "Squamous differentiation/tumor suppressor pathway.",
    },
    "FAT1": {
        "disease_context": "LUSC",
        "category": "tumor_suppressor",
        "notes": "Common LUSC tumor suppressor alteration.",
    },
    "KMT2D": {
        "disease_context": "LUSC",
        "category": "chromatin_modifier",
        "notes": "Chromatin modifier alteration.",
    },
    "KMT2C": {
        "disease_context": "LUSC",
        "category": "chromatin_modifier",
        "notes": "Chromatin modifier alteration.",
    },
}

# RPPA target names are antibody/protein labels rather than always HGNC symbols.
# Keep this mapping conservative and avoid broad substring matching.
RPPA_TARGET_TO_GENE: dict[str, str] = {
    "BRAF": "BRAF",
    "BRAF_pS445": "BRAF",
    "CMET": "MET",
    "CMET_pY1235": "MET",
    "EGFR": "EGFR",
    "EGFR_pY1068": "EGFR",
    "EGFR_pY1173": "EGFR",
    "HER2": "ERBB2",
    "HER2_pY1248": "ERBB2",
    "LKB1": "STK11",
    "NOTCH1": "NOTCH1",
    "Notch1-cleaved": "NOTCH1",
    "NRF2": "NFE2L2",
    "P16INK4A": "CDKN2A",
    "P53": "TP53",
    "P63": "TP63",
    "PI3KP110ALPHA": "PIK3CA",
    "PTEN": "PTEN",
    "RET_pY905": "RET",
    "Sox2": "SOX2",
}

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

PROTEIN_FIELDS = [
    "project_id",
    "case_submitter_id",
    "case_id",
    "sample_submitter_ids",
    "sample_types",
    "aliquot_submitter_ids",
    "file_id",
    "file_name",
    "gene",
    "peptide_target",
    "agid",
    "lab_id",
    "catalog_number",
    "set_id",
    "protein_expression",
]

TARGET_FIELD = [
    "gene",
    "disease_context",
    "category",
    "notes",
    "has_rppa_target",
    "rppa_targets",
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


def _post(endpoint: str, payload: dict[str, Any], *, retries: int = 4) -> Any:
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


def _download_text(url: str, *, gzip_file: bool = False, retries: int = 4) -> io.TextIOBase:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                raw = resp.read()
            if gzip_file:
                return io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)))
            return io.StringIO(raw.decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            last_err = err
            wait = 4 * (2**attempt)
            if attempt == retries - 1:
                raise RuntimeError(f"download failed for {url}: {last_err}") from err
            time.sleep(wait)
    raise RuntimeError(f"download failed for {url}: {last_err}")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _unique_join(values: list[Any]) -> str | None:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue
        text = str(value)
        if text not in seen:
            seen.add(text)
            out.append(text)
    return "; ".join(out) if out else None


def _case_parts(hit_or_row: dict[str, Any]) -> dict[str, Any]:
    if "cases" not in hit_or_row:
        return {
            "case_submitter_id": hit_or_row.get("case_submitter_id"),
            "case_id": hit_or_row.get("case_id"),
            "project_id": hit_or_row.get("project_id"),
            "sample_submitter_ids": hit_or_row.get("sample_submitter_ids"),
            "sample_types": hit_or_row.get("sample_types"),
            "aliquot_submitter_ids": hit_or_row.get("aliquot_submitter_ids"),
        }

    case = _as_list(hit_or_row.get("cases"))[0] if hit_or_row.get("cases") else {}
    samples = _as_list(case.get("samples"))
    aliquots: list[str] = []
    for sample in samples:
        for portion in _as_list(sample.get("portions")):
            for analyte in _as_list(portion.get("analytes")):
                for aliquot in _as_list(analyte.get("aliquots")):
                    aliquots.append(aliquot.get("submitter_id"))
    return {
        "case_submitter_id": case.get("submitter_id"),
        "case_id": case.get("case_id"),
        "project_id": (case.get("project") or {}).get("project_id"),
        "sample_submitter_ids": _unique_join([s.get("submitter_id") for s in samples]),
        "sample_types": _unique_join([s.get("sample_type") for s in samples]),
        "aliquot_submitter_ids": _unique_join(aliquots),
    }


def _flatten_file_hit(hit: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        **_case_parts(hit),
        "molecular_data_kind": kind,
        "file_id": hit.get("file_id"),
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
        "download_url": f"{GDC_DATA_ENDPOINT}/{hit.get('file_id')}",
    }


def fetch_protein_file_index(case_ids: list[str]) -> list[dict[str, Any]]:
    filters = {
        "op": "and",
        "content": [
            {"op": "in", "content": {"field": "cases.case_id", "value": case_ids}},
            {
                "op": "in",
                "content": {
                    "field": "files.data_type",
                    "value": ["Protein Expression Quantification"],
                },
            },
        ],
    }
    payload = {
        "filters": filters,
        "fields": ",".join(FILE_FIELDS),
        "format": "JSON",
        "size": 100000,
    }
    result = _post(GDC_FILES_ENDPOINT, payload)
    return [_flatten_file_hit(hit, "protein") for hit in result["data"]["hits"]]


def load_case_ids(patient_metadata: Path) -> list[str]:
    records = json.loads(patient_metadata.read_text())
    return sorted({row["case_id"] for row in records})


def load_molecular_index(path: Path, kind: str) -> list[dict[str, Any]]:
    with path.open(newline="") as fh:
        return [row for row in csv.DictReader(fh) if row["molecular_data_kind"] == kind]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def extract_mutations(file_row: dict[str, Any], genes: set[str]) -> list[dict[str, Any]]:
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
        if gene not in genes:
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


def extract_rna(file_row: dict[str, Any], genes: set[str]) -> list[dict[str, Any]]:
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
            if gene not in genes:
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


def extract_protein(file_row: dict[str, Any]) -> list[dict[str, Any]]:
    url = file_row.get("download_url") or f"{GDC_DATA_ENDPOINT}/{file_row['file_id']}"
    rows: list[dict[str, Any]] = []
    parts = _case_parts(file_row)
    with _download_text(url) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            target = record.get("peptide_target")
            gene = RPPA_TARGET_TO_GENE.get(target or "")
            if not gene:
                continue
            rows.append(
                {
                    **parts,
                    "file_id": file_row.get("file_id"),
                    "file_name": file_row.get("file_name"),
                    "gene": gene,
                    "peptide_target": target,
                    "agid": record.get("AGID"),
                    "lab_id": record.get("lab_id"),
                    "catalog_number": record.get("catalog_number"),
                    "set_id": record.get("set_id"),
                    "protein_expression": record.get("protein_expression"),
                }
            )
    return rows


def run_parallel(
    label: str,
    files: list[dict[str, Any]],
    worker,
    workers: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, row): row for row in files}
        for fut in as_completed(futures):
            file_row = futures[fut]
            done += 1
            try:
                extracted = fut.result()
                rows.extend(extracted)
            except Exception as err:  # pragma: no cover - runtime data/API failure
                raise RuntimeError(f"{label} extraction failed for {file_row.get('file_name')}: {err}") from err
            if done % 100 == 0 or done == len(files):
                print(f"  {label}: processed {done}/{len(files)} files, rows={len(rows)}")
    return rows


def summarize(
    mutation_rows: list[dict[str, Any]],
    rna_rows: list[dict[str, Any]],
    protein_rows: list[dict[str, Any]],
    mutation_files: list[dict[str, Any]],
    rna_files: list[dict[str, Any]],
    protein_files: list[dict[str, Any]],
) -> dict[str, Any]:
    mutation_gene_project_cases: dict[tuple[str, str], set[str]] = defaultdict(set)
    mutation_gene_cases: dict[str, set[str]] = defaultdict(set)
    mutation_classes: Counter[tuple[str, str]] = Counter()
    for row in mutation_rows:
        case_id = row.get("case_id")
        gene = row["gene"]
        project = row.get("project_id") or "missing"
        if case_id:
            mutation_gene_project_cases[(gene, project)].add(case_id)
            mutation_gene_cases[gene].add(case_id)
        mutation_classes[(gene, row.get("variant_classification") or "missing")] += 1

    expression_gene_project_samples: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rna_rows:
        key = row.get("aliquot_submitter_ids") or row.get("sample_submitter_ids") or row.get("file_id")
        expression_gene_project_samples[(row["gene"], row.get("project_id") or "missing")].add(key)

    protein_gene_project_samples: dict[tuple[str, str], set[str]] = defaultdict(set)
    protein_target_counts: Counter[tuple[str, str]] = Counter()
    for row in protein_rows:
        key = row.get("aliquot_submitter_ids") or row.get("sample_submitter_ids") or row.get("file_id")
        protein_gene_project_samples[(row["gene"], row.get("project_id") or "missing")].add(key)
        protein_target_counts[(row["gene"], row["peptide_target"])] += 1

    return {
        "generated_unix": int(time.time()),
        "target_gene_count": len(IMPORTANT_GENES),
        "target_genes": sorted(IMPORTANT_GENES),
        "input_file_counts": {
            "mutation_maf_files": len(mutation_files),
            "rna_expression_files": len(rna_files),
            "protein_rppa_files": len(protein_files),
        },
        "output_row_counts": {
            "important_mutation_rows": len(mutation_rows),
            "important_rna_expression_rows": len(rna_rows),
            "important_protein_expression_rows": len(protein_rows),
        },
        "mutation_cases_by_gene": {
            gene: len(cases) for gene, cases in sorted(mutation_gene_cases.items())
        },
        "mutation_cases_by_gene_project": {
            f"{gene}|{project}": len(cases)
            for (gene, project), cases in sorted(mutation_gene_project_cases.items())
        },
        "mutation_variant_classification_counts": {
            f"{gene}|{classification}": count
            for (gene, classification), count in sorted(mutation_classes.items())
        },
        "rna_sample_counts_by_gene_project": {
            f"{gene}|{project}": len(samples)
            for (gene, project), samples in sorted(expression_gene_project_samples.items())
        },
        "protein_sample_counts_by_gene_project": {
            f"{gene}|{project}": len(samples)
            for (gene, project), samples in sorted(protein_gene_project_samples.items())
        },
        "protein_target_row_counts": {
            f"{gene}|{target}": count for (gene, target), count in sorted(protein_target_counts.items())
        },
        "notes": [
            "RNA rows are STAR gene-count quantifications from public GDC files.",
            "Protein rows are RPPA antibody/protein targets mapped conservatively to important genes.",
            "MAF mutation rows capture SNVs/indels; fusions and copy-number amplifications require additional data types.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_dir = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=default_dir)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_dir / "important_lung_genes",
        help="Directory for focused output tables.",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-rna", action="store_true", help="Skip RNA extraction.")
    parser.add_argument("--skip-mutations", action="store_true", help="Skip MAF extraction.")
    parser.add_argument("--skip-protein", action="store_true", help="Skip RPPA extraction.")
    args = parser.parse_args()

    genes = set(IMPORTANT_GENES)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    patient_metadata = args.data_dir / "patient_metadata.tcga_lung.json"
    molecular_index = args.data_dir / "molecular_files.tcga_lung.csv"
    case_ids = load_case_ids(patient_metadata)
    mutation_files = load_molecular_index(molecular_index, "mutation")
    rna_files = load_molecular_index(molecular_index, "expression")

    print(f"Target genes: {len(genes)}")
    print(f"Slide-cohort cases: {len(case_ids)}")

    protein_files: list[dict[str, Any]] = []
    if not args.skip_protein:
        print("Fetching public RPPA protein file index from GDC ...")
        protein_files = fetch_protein_file_index(case_ids)
        write_json(args.out_dir / "important_protein_file_index.tcga_lung.json", protein_files)
        write_csv(
            args.out_dir / "important_protein_file_index.tcga_lung.csv",
            protein_files,
            [
                "molecular_data_kind",
                "project_id",
                "case_submitter_id",
                "case_id",
                "sample_submitter_ids",
                "sample_types",
                "aliquot_submitter_ids",
                "file_id",
                "file_name",
                "file_size",
                "md5sum",
                "data_type",
                "data_format",
                "experimental_strategy",
                "access",
                "workflow_type",
                "download_url",
            ],
        )

    targets = []
    rppa_by_gene: dict[str, list[str]] = defaultdict(list)
    for target, gene in RPPA_TARGET_TO_GENE.items():
        rppa_by_gene[gene].append(target)
    for gene, info in sorted(IMPORTANT_GENES.items()):
        rppa_targets = sorted(rppa_by_gene.get(gene, []))
        targets.append(
            {
                "gene": gene,
                **info,
                "has_rppa_target": bool(rppa_targets),
                "rppa_targets": "; ".join(rppa_targets) if rppa_targets else None,
            }
        )
    write_csv(args.out_dir / "important_lung_cancer_genes.csv", targets, TARGET_FIELD)
    write_json(args.out_dir / "important_lung_cancer_genes.json", targets)

    mutation_rows: list[dict[str, Any]] = []
    if not args.skip_mutations:
        print(f"Extracting important-gene mutations from {len(mutation_files)} MAF files ...")
        mutation_rows = run_parallel(
            "mutations",
            mutation_files,
            lambda row: extract_mutations(row, genes),
            args.workers,
        )
        mutation_rows.sort(
            key=lambda row: (
                row.get("project_id") or "",
                row.get("case_submitter_id") or "",
                row.get("gene") or "",
                row.get("chromosome") or "",
                int(row.get("start_position") or 0),
            )
        )
        write_csv(args.out_dir / "important_mutations.tcga_lung.csv", mutation_rows, MUTATION_FIELDS)
        write_json(args.out_dir / "important_mutations.tcga_lung.json", mutation_rows)

    rna_rows: list[dict[str, Any]] = []
    if not args.skip_rna:
        print(f"Extracting important-gene RNA expression from {len(rna_files)} STAR-count files ...")
        rna_rows = run_parallel(
            "rna",
            rna_files,
            lambda row: extract_rna(row, genes),
            args.workers,
        )
        rna_rows.sort(
            key=lambda row: (
                row.get("project_id") or "",
                row.get("case_submitter_id") or "",
                row.get("sample_submitter_ids") or "",
                row.get("gene") or "",
            )
        )
        write_csv(args.out_dir / "important_gene_expression.tcga_lung.csv", rna_rows, RNA_FIELDS)
        write_json(args.out_dir / "important_gene_expression.tcga_lung.json", rna_rows)

    protein_rows: list[dict[str, Any]] = []
    if not args.skip_protein:
        print(f"Extracting important-gene protein expression from {len(protein_files)} RPPA files ...")
        protein_rows = run_parallel("protein", protein_files, extract_protein, args.workers)
        protein_rows.sort(
            key=lambda row: (
                row.get("project_id") or "",
                row.get("case_submitter_id") or "",
                row.get("gene") or "",
                row.get("peptide_target") or "",
            )
        )
        write_csv(
            args.out_dir / "important_protein_expression.tcga_lung.csv",
            protein_rows,
            PROTEIN_FIELDS,
        )
        write_json(args.out_dir / "important_protein_expression.tcga_lung.json", protein_rows)

    summary = summarize(mutation_rows, rna_rows, protein_rows, mutation_files, rna_files, protein_files)
    write_json(args.out_dir / "important_lung_gene_summary.tcga_lung.json", summary)

    print("\nWrote focused important-gene outputs to:")
    print(f"  {args.out_dir}")
    print(json.dumps(summary["output_row_counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
