#!/usr/bin/env python3
"""Download all available TCGA genomic files for the 20 representative patients.

Fetches open-access GDC data including:
* masked somatic MAF files (WXS whole-exome, not WGS),
* copy-number segment and gene-level copy-number files,
* DNA methylation beta values,
* miRNA expression quantification,
and builds genome-wide mutation map summaries from the MAFs.

Raw downloads are stored under ``genomic_data/raw_files/`` (gitignored).
Parsed tables, manifests, and mutation maps are written alongside them.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import shutil
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
CHUNK = 1024 * 1024

DATA_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATA_DIR.parent.parent

GENOMIC_CATEGORIES = {
    "maf": {
        "data_category": "Simple Nucleotide Variation",
        "data_type": "Masked Somatic Mutation",
    },
    "copy_number_segment": {
        "data_category": "Copy Number Variation",
        "data_types": [
            "Copy Number Segment",
            "Masked Copy Number Segment",
            "Allele-specific Copy Number Segment",
        ],
    },
    "gene_level_copy_number": {
        "data_category": "Copy Number Variation",
        "data_type": "Gene Level Copy Number",
    },
    "methylation": {
        "data_category": "DNA Methylation",
        "data_type": "Methylation Beta Value",
    },
    "mirna": {
        "data_category": "Transcriptome Profiling",
        "data_type": "miRNA Expression Quantification",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def gdc_post(payload: dict[str, Any], *, retries: int = 4) -> Any:
    data = json.dumps(payload).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                GDC_FILES_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as err:
            last_err = err
            time.sleep(4 * (2**attempt))
    raise RuntimeError(f"GDC request failed: {last_err}")


def flatten_file_hit(hit: dict[str, Any]) -> dict[str, Any]:
    cases = hit.get("cases") or []
    case = cases[0] if cases else {}
    samples = case.get("samples") or []
    sample_ids: list[str] = []
    sample_types: list[str] = []
    aliquot_ids: list[str] = []
    for sample in samples:
        if sample.get("submitter_id"):
            sample_ids.append(sample["submitter_id"])
        if sample.get("sample_type"):
            sample_types.append(sample["sample_type"])
        for portion in sample.get("portions") or []:
            for analyte in portion.get("analytes") or []:
                for aliquot in analyte.get("aliquots") or []:
                    if aliquot.get("submitter_id"):
                        aliquot_ids.append(aliquot["submitter_id"])
    return {
        "file_id": hit.get("id"),
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
        "case_id": case.get("case_id"),
        "case_submitter_id": case.get("submitter_id"),
        "project_id": (case.get("project") or {}).get("project_id"),
        "sample_submitter_ids": "; ".join(sample_ids),
        "sample_types": "; ".join(sample_types),
        "aliquot_submitter_ids": "; ".join(aliquot_ids),
        "download_url": f"{GDC_DATA_ENDPOINT}/{hit.get('id')}",
    }


def fetch_files(case_ids: list[str]) -> list[dict[str, Any]]:
    payload = {
        "filters": {
            "op": "and",
            "content": [
                {"op": "in", "content": {"field": "cases.case_id", "value": case_ids}},
                {"op": "in", "content": {"field": "access", "value": ["open"]}},
            ],
        },
        "fields": ",".join(
            [
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
        ),
        "format": "JSON",
        "size": 10000,
    }
    result = gdc_post(payload)
    return [flatten_file_hit(hit) for hit in result["data"]["hits"]]


def classify_file(row: dict[str, Any]) -> str | None:
    cat = row.get("data_category") or ""
    dtype = row.get("data_type") or ""
    if cat == "Simple Nucleotide Variation" and dtype == "Masked Somatic Mutation":
        return "maf"
    if cat == "Copy Number Variation":
        if dtype == "Gene Level Copy Number":
            return "gene_level_copy_number"
        if dtype in {
            "Copy Number Segment",
            "Masked Copy Number Segment",
            "Allele-specific Copy Number Segment",
        }:
            return "copy_number_segment"
    if cat == "DNA Methylation" and dtype == "Methylation Beta Value":
        return "methylation"
    if cat == "Transcriptome Profiling" and dtype == "miRNA Expression Quantification":
        return "mirna"
    return None


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    out = ["id\tfilename\tmd5\tsize\tstate"]
    for row in rows:
        out.append(
            f"{row['file_id']}\t{row['file_name']}\t{row.get('md5sum','')}\t{row.get('file_size','')}\t{row.get('state','')}"
        )
    path.write_text("\n".join(out) + "\n")


def download_file(row: dict[str, Any], dest: Path, *, verify_md5: bool = True) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = row["download_url"]
    tmp = dest.with_suffix(dest.suffix + ".part")
    mode = "ab" if tmp.exists() else "wb"
    offset = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url)
    if offset:
        req.add_header("Range", f"bytes={offset}-")
    with urllib.request.urlopen(req, timeout=300) as resp:
        with tmp.open(mode) as fh:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
    if verify_md5 and row.get("md5sum"):
        md5 = hashlib.md5()
        with tmp.open("rb") as fh:
            for chunk in iter(lambda: fh.read(CHUNK), b""):
                md5.update(chunk)
        if md5.hexdigest() != row["md5sum"]:
            raise RuntimeError(f"MD5 mismatch for {dest.name}")
    tmp.rename(dest)
    return dest


def download_many(label: str, rows: list[dict[str, Any]], dest_fn, workers: int) -> list[Path]:
    paths: list[Path] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_file, row, dest_fn(row)): row for row in rows}
        for fut in as_completed(futures):
            row = futures[fut]
            done += 1
            path = fut.result()
            paths.append(path)
            print(f"  {label}: {done}/{len(rows)} {row.get('case_submitter_id')} -> {path.name}")
    return paths


def parse_maf_for_maps(path: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    opener = gzip.open if str(path).endswith(".gz") else open
    rows: list[dict[str, Any]] = []
    with opener(path, "rt") as fh:
        header: list[str] | None = None
        for line in fh:
            if line.startswith("#"):
                continue
            if header is None:
                header = line.rstrip("\n").split("\t")
                continue
            record = dict(zip(header, line.rstrip("\n").split("\t")))
            chrom = record.get("Chromosome", "")
            start = record.get("Start_Position", "")
            end = record.get("End_Position", "")
            try:
                start_i = int(start)
                end_i = int(end)
            except (TypeError, ValueError):
                start_i = end_i = None
            bin_start = (start_i // 1_000_000) * 1_000_000 if start_i is not None else None
            rows.append(
                {
                    "case_submitter_id": meta.get("case_submitter_id"),
                    "case_id": meta.get("case_id"),
                    "project_id": meta.get("project_id"),
                    "file_id": meta.get("file_id"),
                    "file_name": meta.get("file_name"),
                    "chromosome": chrom,
                    "start_position": start,
                    "end_position": end,
                    "genome_bin_1mb_start": bin_start,
                    "gene": record.get("Hugo_Symbol"),
                    "variant_classification": record.get("Variant_Classification"),
                    "variant_type": record.get("Variant_Type"),
                    "reference_allele": record.get("Reference_Allele"),
                    "tumor_seq_allele1": record.get("Tumor_Seq_Allele1"),
                    "tumor_seq_allele2": record.get("Tumor_Seq_Allele2"),
                    "hgvsp_short": record.get("HGVSp_Short"),
                    "tumor_sample_barcode": record.get("Tumor_Sample_Barcode"),
                    "t_depth": record.get("t_depth"),
                    "t_alt_count": record.get("t_alt_count"),
                }
            )
    return rows


def parse_copy_number_segments(path: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            rows.append(
                {
                    "case_submitter_id": meta.get("case_submitter_id"),
                    "case_id": meta.get("case_id"),
                    "project_id": meta.get("project_id"),
                    "file_id": meta.get("file_id"),
                    "file_name": meta.get("file_name"),
                    "data_type": meta.get("data_type"),
                    "experimental_strategy": meta.get("experimental_strategy"),
                    "chromosome": record.get("Chromosome") or record.get("chromosome"),
                    "start": record.get("Start") or record.get("start"),
                    "end": record.get("End") or record.get("end"),
                    "num_probes": record.get("Num_Probes") or record.get("num_probes"),
                    "segment_mean": record.get("Segment_Mean") or record.get("segment_mean"),
                    "copy_number": record.get("Copy_Number") or record.get("copy_number"),
                    "major_copy_number": record.get("Major_Copy_Number") or record.get("major_copy_number"),
                    "minor_copy_number": record.get("Minor_Copy_Number") or record.get("minor_copy_number"),
                }
            )
    return rows


def parse_gene_level_cn(path: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            rows.append(
                {
                    "case_submitter_id": meta.get("case_submitter_id"),
                    "case_id": meta.get("case_id"),
                    "project_id": meta.get("project_id"),
                    "file_id": meta.get("file_id"),
                    "file_name": meta.get("file_name"),
                    "experimental_strategy": meta.get("experimental_strategy"),
                    "gene_id": record.get("gene_id") or record.get("Gene_Id"),
                    "gene_name": record.get("gene_name") or record.get("Gene_Symbol") or record.get("gene"),
                    "copy_number": record.get("copy_number") or record.get("Copy_Number"),
                    "copy_number_log2": record.get("copy_number_log2") or record.get("Log2_Copy_Number"),
                }
            )
    return rows


def parse_mirna(path: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            mirna = record.get("miRNA_ID") or record.get("mirna_id") or record.get("read_name")
            if not mirna:
                continue
            rows.append(
                {
                    "case_submitter_id": meta.get("case_submitter_id"),
                    "case_id": meta.get("case_id"),
                    "project_id": meta.get("project_id"),
                    "file_id": meta.get("file_id"),
                    "file_name": meta.get("file_name"),
                    "mirna_id": mirna,
                    "read_count": record.get("read_count") or record.get("reads_per_million_miRNA_mapped"),
                    "unmapped": record.get("unmapped"),
                }
            )
    return rows


def summarize_bins(mutation_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str, int | None]] = Counter()
    for row in mutation_rows:
        key = (
            row.get("case_submitter_id") or "",
            row.get("project_id") or "",
            row.get("chromosome") or "",
            row.get("genome_bin_1mb_start"),
        )
        counts[key] += 1
    out = []
    for (case, project, chrom, bin_start), count in sorted(counts.items()):
        out.append(
            {
                "case_submitter_id": case,
                "project_id": project,
                "chromosome": chrom,
                "genome_bin_1mb_start": bin_start,
                "genome_bin_1mb_end": (bin_start + 999_999) if bin_start is not None else None,
                "mutation_count": count,
            }
        )
    return out


def summarize_by_chromosome(mutation_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in mutation_rows:
        counts[(row.get("case_submitter_id") or "", row.get("project_id") or "", row.get("chromosome") or "")] += 1
    return [
        {
            "case_submitter_id": case,
            "project_id": project,
            "chromosome": chrom,
            "mutation_count": count,
        }
        for (case, project, chrom), count in sorted(counts.items())
    ]


def summarize_top_genes(mutation_rows: list[dict[str, Any]], *, top_n: int = 50) -> list[dict[str, Any]]:
    by_patient: dict[str, Counter[str]] = defaultdict(Counter)
    for row in mutation_rows:
        gene = row.get("gene") or "Unknown"
        case = row.get("case_submitter_id") or ""
        by_patient[case][gene] += 1
    out: list[dict[str, Any]] = []
    for case, counter in sorted(by_patient.items()):
        project = next((r.get("project_id") for r in mutation_rows if r.get("case_submitter_id") == case), "")
        for rank, (gene, count) in enumerate(counter.most_common(top_n), start=1):
            out.append(
                {
                    "case_submitter_id": case,
                    "project_id": project,
                    "rank": rank,
                    "gene": gene,
                    "mutation_count": count,
                }
            )
    return out


def summarize_variant_classes(mutation_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in mutation_rows:
        counts[
            (
                row.get("case_submitter_id") or "",
                row.get("project_id") or "",
                row.get("variant_classification") or "Unknown",
            )
        ] += 1
    return [
        {
            "case_submitter_id": case,
            "project_id": project,
            "variant_classification": vclass,
            "mutation_count": count,
        }
        for (case, project, vclass), count in sorted(counts.items())
    ]


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
        default=REPO_ROOT / "demo" / "genomic_data",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-methylation", action="store_true", help="Skip ~300MB methylation beta downloads.")
    args = parser.parse_args()

    patients = read_csv(args.representative_csv)
    case_ids = sorted({p["case_id"] for p in patients})
    submitter_by_case = {p["case_id"]: p["case_submitter_id"] for p in patients}

    print(f"Querying GDC for {len(case_ids)} representative cases ...")
    all_files = fetch_files(case_ids)
    genomic_files = []
    for row in all_files:
        kind = classify_file(row)
        if kind:
            row["genomic_kind"] = kind
            genomic_files.append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out_dir / "raw_files"
    maps_dir = args.out_dir / "mutation_maps"
    parsed_dir = args.out_dir / "parsed_tables"
    maps_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    index_fields = list(genomic_files[0].keys()) + ["genomic_kind"] if genomic_files else []
    write_csv(args.out_dir / "genomic_file_index.csv", genomic_files, index_fields)
    write_json(args.out_dir / "genomic_file_index.json", genomic_files)

    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in genomic_files:
        by_kind[row["genomic_kind"]].append(row)

    if args.skip_methylation:
        by_kind["methylation"] = []

    for kind, rows in by_kind.items():
        write_manifest(args.out_dir / f"gdc_manifest.{kind}.txt", rows)

    all_genomic = [r for kind_rows in by_kind.values() for r in kind_rows]
    write_manifest(args.out_dir / "gdc_manifest.all_genomic.txt", all_genomic)

    availability = []
    for patient in patients:
        cid = patient["case_id"]
        sid = patient["case_submitter_id"]
        pf = [r for r in genomic_files if r.get("case_id") == cid]
        availability.append(
            {
                "case_submitter_id": sid,
                "case_id": cid,
                "project_id": patient["project_id"],
                "maf_files": sum(1 for r in pf if r["genomic_kind"] == "maf"),
                "copy_number_segment_files": sum(1 for r in pf if r["genomic_kind"] == "copy_number_segment"),
                "gene_level_copy_number_files": sum(1 for r in pf if r["genomic_kind"] == "gene_level_copy_number"),
                "methylation_files": sum(1 for r in pf if r["genomic_kind"] == "methylation"),
                "mirna_files": sum(1 for r in pf if r["genomic_kind"] == "mirna"),
                "total_genomic_files": len(pf),
            }
        )
    write_csv(args.out_dir / "genomic_availability_summary.csv", availability, list(availability[0].keys()))
    write_json(args.out_dir / "genomic_availability_summary.json", availability)

    mutation_map_rows: list[dict[str, Any]] = []
    cn_rows: list[dict[str, Any]] = []
    gene_cn_rows: list[dict[str, Any]] = []
    mirna_rows: list[dict[str, Any]] = []

    if not args.skip_download:
        def maf_dest(row: dict[str, Any]) -> Path:
            sid = row.get("case_submitter_id") or submitter_by_case.get(row.get("case_id"), "unknown")
            return raw_dir / "maf" / sid / row["file_name"]

        def generic_dest(kind: str, row: dict[str, Any]) -> Path:
            sid = row.get("case_submitter_id") or submitter_by_case.get(row.get("case_id"), "unknown")
            return raw_dir / kind / sid / row["file_name"]

        if by_kind["maf"]:
            print(f"Downloading {len(by_kind['maf'])} MAF files ...")
            maf_paths = download_many("maf", by_kind["maf"], maf_dest, args.workers)
            for row, path in zip(by_kind["maf"], maf_paths):
                mutation_map_rows.extend(parse_maf_for_maps(path, row))

        for kind, parser in [
            ("copy_number_segment", parse_copy_number_segments),
            ("gene_level_copy_number", parse_gene_level_cn),
        ]:
            rows = by_kind.get(kind, [])
            if not rows:
                continue
            print(f"Downloading {len(rows)} {kind} files ...")
            paths = download_many(kind, rows, lambda r, k=kind: generic_dest(k, r), args.workers)
            for row, path in zip(rows, paths):
                parsed = parser(path, row)
                if kind == "copy_number_segment":
                    cn_rows.extend(parsed)
                else:
                    gene_cn_rows.extend(parsed)

        if by_kind.get("mirna"):
            print(f"Downloading {len(by_kind['mirna'])} miRNA files ...")
            paths = download_many("mirna", by_kind["mirna"], lambda r: generic_dest("mirna", r), args.workers)
            for row, path in zip(by_kind["mirna"], paths):
                mirna_rows.extend(parse_mirna(path, row))

        if by_kind.get("methylation"):
            print(f"Downloading {len(by_kind['methylation'])} methylation beta files ...")
            download_many(
                "methylation",
                by_kind["methylation"],
                lambda r: generic_dest("methylation", r),
                args.workers,
            )

    # Write mutation maps and parsed tables.
    if mutation_map_rows:
        map_fields = list(mutation_map_rows[0].keys())
        write_csv(maps_dir / "genome_mutation_landscape.csv", mutation_map_rows, map_fields)
        write_csv(maps_dir / "mutations_by_chromosome.csv", summarize_by_chromosome(mutation_map_rows), ["case_submitter_id", "project_id", "chromosome", "mutation_count"])
        write_csv(
            maps_dir / "mutations_by_1mb_bin.csv",
            summarize_bins(mutation_map_rows),
            ["case_submitter_id", "project_id", "chromosome", "genome_bin_1mb_start", "genome_bin_1mb_end", "mutation_count"],
        )
        write_csv(
            maps_dir / "top_mutated_genes_by_patient.csv",
            summarize_top_genes(mutation_map_rows),
            ["case_submitter_id", "project_id", "rank", "gene", "mutation_count"],
        )
        write_csv(
            maps_dir / "variant_classification_summary.csv",
            summarize_variant_classes(mutation_map_rows),
            ["case_submitter_id", "project_id", "variant_classification", "mutation_count"],
        )

    if cn_rows:
        write_csv(parsed_dir / "copy_number_segments.csv", cn_rows, list(cn_rows[0].keys()))
    if gene_cn_rows:
        write_csv(parsed_dir / "gene_level_copy_number.csv", gene_cn_rows, list(gene_cn_rows[0].keys()))
    if mirna_rows:
        write_csv(parsed_dir / "mirna_expression.csv", mirna_rows, list(mirna_rows[0].keys()))

    summary = {
        "patient_count": len(patients),
        "genomic_files_indexed": len(genomic_files),
        "files_by_kind": {kind: len(rows) for kind, rows in by_kind.items()},
        "downloaded_maf_files": len(by_kind.get("maf", [])),
        "mutation_landscape_rows": len(mutation_map_rows),
        "copy_number_segment_rows": len(cn_rows),
        "gene_level_copy_number_rows": len(gene_cn_rows),
        "mirna_rows": len(mirna_rows),
        "output_directory": str(args.out_dir),
        "important_limitations": [
            "TCGA-LUAD/LUSC somatic mutation MAF files are from WXS (whole-exome sequencing), not whole-genome sequencing (WGS).",
            "Genome-wide mutation maps here cover exome-captured regions (~1-2% of the genome), not the full 3 Gb genome.",
            "Copy-number data is mostly from SNP6 genotyping arrays; a small number of WGS-based CN segments exist for subset of cases.",
            "Methylation beta-value files are EPIC/450K probe-level tables (~300 MB total).",
            "Structural variants, gene fusions, and low-frequency variants may be absent from open MAF files.",
        ],
        "raw_file_locations": {
            "maf": str(raw_dir / "maf"),
            "copy_number_segment": str(raw_dir / "copy_number_segment"),
            "gene_level_copy_number": str(raw_dir / "gene_level_copy_number"),
            "methylation": str(raw_dir / "methylation"),
            "mirna": str(raw_dir / "mirna"),
        },
    }
    write_json(args.out_dir / "genomic_package_summary.json", summary)

    readme = f"""# Representative 20-patient TCGA genomic data package

## Important: exome vs whole genome

TCGA lung open somatic mutation files are **WXS (whole-exome)** MAFs, not true
whole-genome (WGS) mutation calls. Mutation maps in this folder therefore reflect
**exome-covered regions**, not the entire 3 Gb genome.

Available open-access genomic modalities for these 20 patients:

| Modality | Files | Notes |
|----------|------:|-------|
| Masked somatic MAF (WXS) | {len(by_kind.get('maf', []))} | Raw `.maf.gz` in `raw_files/maf/` |
| Copy-number segments | {len(by_kind.get('copy_number_segment', []))} | SNP6 array + limited WGS segments |
| Gene-level copy number | {len(by_kind.get('gene_level_copy_number', []))} | Parsed to `parsed_tables/` |
| DNA methylation beta | {len(by_kind.get('methylation', []))} | Raw files in `raw_files/methylation/` |
| miRNA expression | {len(by_kind.get('mirna', []))} | Parsed to `parsed_tables/mirna_expression.csv` |

## Regenerate

```bash
python3 data/tcga_lung/download_representative_genomic_data.py --workers 8
```

Use `--skip-methylation` to omit ~300 MB methylation downloads.

## Mutation maps

- `mutation_maps/genome_mutation_landscape.csv` — every MAF variant with chromosome coordinates
- `mutation_maps/mutations_by_chromosome.csv` — per-patient chromosome counts
- `mutation_maps/mutations_by_1mb_bin.csv` — 1 Mb genome bins (exome-covered loci)
- `mutation_maps/top_mutated_genes_by_patient.csv`
- `mutation_maps/variant_classification_summary.csv`

## Manifests

GDC download manifests for gdc-client or `download.py`:

- `gdc_manifest.all_genomic.txt`
- `gdc_manifest.maf.txt`
- `gdc_manifest.copy_number_segment.txt`
- etc.
"""
    (args.out_dir / "README.md").write_text(readme)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
