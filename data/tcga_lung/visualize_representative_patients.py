#!/usr/bin/env python3
"""Build a visual summary report for the 20 representative TCGA lung patients.

Reads clinical, molecular, and genomic tables under
``representative_patients/data_package/`` and ``representative_patients/genomic_data/``,
then writes:

* summary CSV/JSON tables,
* standalone SVG plots, and
* a self-contained HTML report (``index.html`` + ``gallery.html``).

Uses only the Python standard library plus shared chart helpers from
``visualize_important_lung_genes.py``.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from visualize_important_lung_genes import (
    COLORS,
    MUTATION_DRIVER_ORDER,
    PROJECT_LABELS,
    bar_chart,
    build_treatment_summary,
    count_values,
    esc,
    fmt_num,
    grouped_mutation_chart,
    histogram,
    median,
    read_csv,
    resistance_proxy_counts,
    split_field_counts,
    table_html,
    to_float,
    write_csv,
    write_json,
    write_svg,
    yes_no_field_counts,
)

DRIVER_GENES = MUTATION_DRIVER_ORDER

DATA_LAYER_LABELS = [
    "Clinical",
    "Mutations (MAF)",
    "RNA expression",
    "RPPA protein",
    "CNV segments",
    "miRNA",
    "Methylation",
    "H&E slides",
]


def patient_sort_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("project_id", ""),
        row.get("smoking_group", ""),
        row.get("case_submitter_id", ""),
    )


def binary_matrix_heatmap(
    rows: list[str],
    cols: list[str],
    values: dict[tuple[str, str], float | int | str],
    title: str,
    *,
    width: int = 980,
    cell: int = 18,
    row_label_w: int = 110,
    col_label_h: int = 90,
    color_on: str = "#dc2626",
    color_off: str = "#f1f5f9",
    color_scale: tuple[str, str, str] | None = None,
    show_legend: bool = True,
) -> str:
    left = row_label_w + 10
    top = 54
    chart_w = len(cols) * cell
    chart_h = len(rows) * cell
    height = top + col_label_h + chart_h + 40
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
    ]
    for j, col in enumerate(cols):
        x = left + j * cell + cell / 2
        parts.append(
            f'<text x="{x:.1f}" y="{top + 12}" class="axis-label" '
            f'text-anchor="end" transform="rotate(-55 {x:.1f} {top + 12})">{esc(col)}</text>'
        )
    for i, row in enumerate(rows):
        y = top + col_label_h + i * cell
        parts.append(f'<text x="0" y="{y + cell * 0.72:.1f}" class="axis-label">{esc(row)}</text>')
        for j, col in enumerate(cols):
            val = values.get((row, col), 0)
            x = left + j * cell
            if color_scale and isinstance(val, (int, float)):
                lo, mid, hi = color_scale
                if val <= 0:
                    fill = color_off
                elif val < 0.5:
                    fill = lo
                elif val < 1.0:
                    fill = mid
                else:
                    fill = hi
            elif val:
                fill = color_on
            else:
                fill = color_off
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - 1:.1f}" height="{cell - 1:.1f}" '
                f'fill="{fill}" stroke="#cbd5e1" stroke-width="0.5"></rect>'
            )
    if show_legend:
        ly = top + col_label_h + chart_h + 18
        parts.append(f'<rect x="{left}" y="{ly}" width="14" height="10" fill="{color_on}"></rect>')
        parts.append(f'<text x="{left + 20}" y="{ly + 9}" class="legend">Present / altered</text>')
        parts.append(f'<rect x="{left + 170}" y="{ly}" width="14" height="10" fill="{color_off}"></rect>')
        parts.append(f'<text x="{left + 190}" y="{ly + 9}" class="legend">Absent / not available</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def stacked_bar_chart(
    categories: list[str],
    series: dict[str, list[int]],
    title: str,
    *,
    width: int = 840,
    height: int = 320,
    colors: list[str] | None = None,
) -> str:
    palette = colors or [COLORS["blue"], COLORS["orange"], COLORS["green"], COLORS["purple"]]
    left, bottom, chart_w, chart_h = 55, 240, width - 90, 170
    totals = [sum(series[name][i] for name in series) for i in range(len(categories))]
    max_total = max(totals or [1]) or 1
    bar_w = chart_w / max(len(categories), 1) - 12
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{left + chart_w}" y2="{bottom}" stroke="#94a3b8"></line>',
    ]
    legend_x = left
    for idx, (name, _) in enumerate(series.items()):
        color = palette[idx % len(palette)]
        parts.append(f'<rect x="{legend_x}" y="36" width="14" height="10" fill="{color}"></rect>')
        parts.append(f'<text x="{legend_x + 20}" y="45" class="legend">{esc(name)}</text>')
        legend_x += 120
    for i, cat in enumerate(categories):
        x = left + i * (chart_w / len(categories)) + 6
        y_base = bottom
        for idx, (name, vals) in enumerate(series.items()):
            val = vals[i]
            h = chart_h * val / max_total
            y = y_base - h
            color = palette[idx % len(palette)]
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"></rect>')
            y_base = y
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{bottom + 18}" class="axis-label" text-anchor="middle">{esc(cat)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def horizontal_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    *,
    width: int = 920,
    color: str = COLORS["blue"],
    x_label: str = "",
) -> str:
    left = 130
    right = 70
    top = 54
    row_h = 20
    gap = 6
    height = top + len(labels) * (row_h + gap) + 50
    max_val = max(values or [1]) or 1
    scale_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
    ]
    for i, (label, val) in enumerate(zip(labels, values)):
        y = top + i * (row_h + gap)
        w = scale_w * val / max_val
        parts.append(f'<text x="0" y="{y + 15}" class="axis-label">{esc(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{row_h}" rx="3" fill="{color}"></rect>')
        parts.append(f'<text x="{left + w + 6:.1f}" y="{y + 15}" class="value-label">{fmt_num(val, 0)}</text>')
    if x_label:
        parts.append(f'<text x="{left + scale_w / 2 - 40}" y="{height - 8}" class="axis-label">{esc(x_label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def chromosome_landscape_chart(
    by_chrom: dict[str, Counter[str]],
    title: str,
    *,
    width: int = 980,
    height: int = 360,
) -> str:
    chrom_order = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]
    patients = sorted(by_chrom)
    left, top, chart_w, chart_h = 110, 70, width - 150, 230
    max_count = 1
    for patient in patients:
        for chrom in chrom_order:
            max_count = max(max_count, by_chrom[patient].get(chrom, 0))
    cell_w = chart_w / len(chrom_order)
    cell_h = chart_h / max(len(patients), 1)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
        f'<text x="0" y="44" class="axis-label">Mutation counts per chromosome (darker = more mutations).</text>',
    ]
    for j, chrom in enumerate(chrom_order):
        label = chrom.replace("chr", "")
        x = left + j * cell_w + cell_w / 2
        parts.append(f'<text x="{x:.1f}" y="{top - 8}" class="axis-label" text-anchor="middle">{esc(label)}</text>')
    for i, patient in enumerate(patients):
        y = top + i * cell_h
        short = patient.replace("TCGA-", "")
        parts.append(f'<text x="0" y="{y + cell_h * 0.65:.1f}" class="axis-label">{esc(short)}</text>')
        for j, chrom in enumerate(chrom_order):
            count = by_chrom[patient].get(chrom, 0)
            intensity = count / max_count if max_count else 0
            r = int(255 - 180 * intensity)
            g = int(255 - 220 * intensity)
            b = int(255 - 220 * intensity)
            fill = f"rgb({r},{g},{b})"
            x = left + j * cell_w
            parts.append(
                f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{cell_w - 2:.1f}" height="{cell_h - 2:.1f}" '
                f'fill="{fill}" stroke="#cbd5e1" stroke-width="0.5"></rect>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def build_driver_mutation_matrix(
    mutations: list[dict[str, str]],
    patients: list[str],
) -> tuple[list[str], dict[tuple[str, str], int]]:
    mutated: dict[tuple[str, str], int] = defaultdict(int)
    gene_set: set[str] = set()
    for row in mutations:
        gene = row.get("gene", "")
        patient = row.get("case_submitter_id", "")
        if gene and patient:
            mutated[(patient, gene)] += 1
            gene_set.add(gene)
    genes = [g for g in DRIVER_GENES if g in gene_set]
    genes += sorted(g for g in gene_set if g not in genes)
    return genes, dict(mutated)


def build_mutation_frequency(
    mutations: list[dict[str, str]],
    patient_meta: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    by_gene_project: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in mutations:
        gene = row.get("gene", "")
        patient = row.get("case_submitter_id", "")
        project = row.get("project_id", "")
        if gene and patient:
            by_gene_project[gene][project].add(patient)
    luad_patients = {p for p, r in patient_meta.items() if r.get("project_id") == "TCGA-LUAD"}
    lusc_patients = {p for p, r in patient_meta.items() if r.get("project_id") == "TCGA-LUSC"}
    rows: list[dict[str, Any]] = []
    for gene in DRIVER_GENES:
        if gene not in by_gene_project:
            continue
        luad_mut = by_gene_project[gene].get("TCGA-LUAD", set())
        lusc_mut = by_gene_project[gene].get("TCGA-LUSC", set())
        all_mut = luad_mut | lusc_mut
        rows.append(
            {
                "gene": gene,
                "mutated_cases": len(all_mut),
                "analyzable_cases": len(patient_meta),
                "overall_pct": round(100 * len(all_mut) / len(patient_meta), 1),
                "luad_mutated": len(luad_mut),
                "luad_total": len(luad_patients),
                "luad_pct": round(100 * len(luad_mut) / len(luad_patients), 1) if luad_patients else 0,
                "lusc_mutated": len(lusc_mut),
                "lusc_total": len(lusc_patients),
                "lusc_pct": round(100 * len(lusc_mut) / len(lusc_patients), 1) if lusc_patients else 0,
            }
        )
    return rows


def per_patient_mutation_burden(
    somatic_rows: list[dict[str, str]],
    availability: list[dict[str, str]],
) -> list[dict[str, Any]]:
    counts = Counter(row["case_submitter_id"] for row in somatic_rows if row.get("case_submitter_id"))
    out: list[dict[str, Any]] = []
    for row in availability:
        pid = row["case_submitter_id"]
        out.append(
            {
                "case_submitter_id": pid,
                "project_id": row.get("project_id", ""),
                "somatic_mutation_rows": counts.get(pid, 0),
                "important_gene_mutations": int(float(row.get("important_gene_mutation_rows") or 0)),
            }
        )
    out.sort(key=lambda r: (-r["somatic_mutation_rows"], r["case_submitter_id"]))
    return out


def per_patient_cnv_summary(cnv_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_patient: dict[str, dict[str, int]] = defaultdict(lambda: {"segments": 0, "amp": 0, "del": 0, "neutral": 0})
    for row in cnv_rows:
        pid = row.get("case_submitter_id", "")
        if not pid:
            continue
        by_patient[pid]["segments"] += 1
        cn = to_float(row.get("copy_number"))
        if cn is None:
            continue
        if cn >= 3:
            by_patient[pid]["amp"] += 1
        elif cn <= 1:
            by_patient[pid]["del"] += 1
        else:
            by_patient[pid]["neutral"] += 1
    out = []
    for pid, stats in sorted(by_patient.items()):
        out.append({"case_submitter_id": pid, **stats})
    return out


def per_patient_mirna_summary(mirna_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_patient: dict[str, dict[str, Any]] = defaultdict(lambda: {"mirna_targets": 0, "total_reads": 0})
    for row in mirna_rows:
        pid = row.get("case_submitter_id", "")
        if not pid:
            continue
        by_patient[pid]["mirna_targets"] += 1
        reads = to_float(row.get("read_count")) or 0
        by_patient[pid]["total_reads"] += reads
    return [{"case_submitter_id": pid, **stats} for pid, stats in sorted(by_patient.items())]


def build_data_availability_matrix(
    clinical_rows: list[dict[str, str]],
    data_avail: list[dict[str, str]],
    genomic_avail: list[dict[str, str]],
) -> tuple[list[str], list[str], dict[tuple[str, str], int]]:
    avail_by_patient = {r["case_submitter_id"]: r for r in data_avail}
    gen_by_patient = {r["case_submitter_id"]: r for r in genomic_avail}
    patients = sorted({r["case_submitter_id"] for r in clinical_rows}, key=lambda p: p)
    values: dict[tuple[str, str], int] = {}
    for pid in patients:
        da = avail_by_patient.get(pid, {})
        ga = gen_by_patient.get(pid, {})
        values[(pid, "Clinical")] = 1 if da.get("clinical_fields") else 0
        values[(pid, "Mutations (MAF)")] = 1 if int(float(da.get("mutation_maf_files") or 0)) > 0 else 0
        values[(pid, "RNA expression")] = 1 if int(float(da.get("expression_files") or 0)) > 0 else 0
        values[(pid, "RPPA protein")] = 1 if int(float(da.get("rppa_protein_rows") or 0)) > 0 else 0
        values[(pid, "CNV segments")] = 1 if int(float(ga.get("copy_number_segment_files") or 0)) > 0 else 0
        values[(pid, "miRNA")] = 1 if int(float(ga.get("mirna_files") or 0)) > 0 else 0
        values[(pid, "Methylation")] = 1 if int(float(ga.get("methylation_files") or 0)) > 0 else 0
        values[(pid, "H&E slides")] = 1 if int(float(da.get("slide_files") or 0)) > 0 else 0
    return patients, DATA_LAYER_LABELS, values


def build_master_patient_summary(
    selection: list[dict[str, str]],
    clinical: list[dict[str, str]],
    data_avail: list[dict[str, str]],
    genomic_avail: list[dict[str, str]],
    mutation_burden: list[dict[str, Any]],
    cnv_summary: list[dict[str, Any]],
    mirna_summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    clinical_by = {r["case_submitter_id"]: r for r in clinical}
    avail_by = {r["case_submitter_id"]: r for r in data_avail}
    gen_by = {r["case_submitter_id"]: r for r in genomic_avail}
    burden_by = {r["case_submitter_id"]: r for r in mutation_burden}
    cnv_by = {r["case_submitter_id"]: r for r in cnv_summary}
    mirna_by = {r["case_submitter_id"]: r for r in mirna_summary}
    rows: list[dict[str, Any]] = []
    for sel in sorted(selection, key=patient_sort_key):
        pid = sel["case_submitter_id"]
        clin = clinical_by.get(pid, {})
        da = avail_by.get(pid, {})
        ga = gen_by.get(pid, {})
        burden = burden_by.get(pid, {})
        cnv = cnv_by.get(pid, {})
        mirna = mirna_by.get(pid, {})
        rows.append(
            {
                "case_submitter_id": pid,
                "project_id": sel.get("project_id", ""),
                "smoking_group": sel.get("smoking_group", ""),
                "stratum": sel.get("stratum", ""),
                "selection_rank": sel.get("selection_rank", ""),
                "sex": clin.get("sex") or sel.get("sex", ""),
                "age_at_diagnosis_years": clin.get("age_at_diagnosis_years") or sel.get("age_at_diagnosis_years", ""),
                "ajcc_pathologic_stage": clin.get("ajcc_pathologic_stage") or sel.get("ajcc_pathologic_stage", ""),
                "vital_status": clin.get("vital_status") or sel.get("vital_status", ""),
                "survival_time_days": clin.get("survival_time_days") or sel.get("survival_time_days", ""),
                "survival_event": clin.get("survival_event") or sel.get("survival_event", ""),
                "important_gene_mutations": sel.get("important_gene_mutations", ""),
                "somatic_mutation_rows": burden.get("somatic_mutation_rows", 0),
                "genome_wide_rna_rows": da.get("genome_wide_rna_rows", 0),
                "rppa_protein_rows": da.get("rppa_protein_rows", 0),
                "cnv_segments": cnv.get("segments", 0),
                "cnv_amplifications": cnv.get("amp", 0),
                "cnv_deletions": cnv.get("del", 0),
                "mirna_targets": mirna.get("mirna_targets", 0),
                "methylation_files": ga.get("methylation_files", 0),
                "slide_count": clin.get("slide_count") or sel.get("slide_count", 0),
                "prior_treatment": clin.get("prior_treatment") or sel.get("prior_treatment", ""),
                "treatment_types": clin.get("treatment_types") or sel.get("treatment_types", ""),
                "disease_response": clin.get("disease_response") or sel.get("disease_response", ""),
                "progression_or_recurrence": clin.get("progression_or_recurrence") or sel.get("progression_or_recurrence", ""),
            }
        )
    return rows


def rna_expression_heatmap(
    rna_rows: list[dict[str, str]],
    patients: list[str],
    genes: list[str] | None = None,
) -> tuple[list[str], list[str], dict[tuple[str, str], float]]:
    selected_genes = genes or [g for g in DRIVER_GENES]
    values: dict[tuple[str, str], float] = {}
    for row in rna_rows:
        gene = row.get("gene", "")
        patient = row.get("case_submitter_id", "")
        tpm = to_float(row.get("tpm_unstranded"))
        if gene in selected_genes and patient and tpm is not None:
            key = (patient, gene)
            values[key] = max(values.get(key, 0), tpm)
    # log-scale normalization for color
    max_tpm = max(values.values() or [1])
    normed: dict[tuple[str, str], float] = {}
    import math

    for key, tpm in values.items():
        normed[key] = math.log10(tpm + 1) / math.log10(max_tpm + 1) if max_tpm > 0 else 0
    present_genes = [g for g in selected_genes if any((p, g) in values for p in patients)]
    return patients, present_genes, normed


def render_gallery(plots_dir: Path, written: list[str], title: str) -> None:
    gallery_items = "\n".join(
        f'    <section class="plot-card"><h3>{esc(name)}</h3><img src="plots/{esc(name)}" alt="{esc(name)}"></section>'
        for name in written
    )
    gallery = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
    h1 {{ margin-bottom: 8px; }}
    .subtitle {{ color: #475569; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(520px, 1fr)); gap: 20px; }}
    .plot-card {{ background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }}
    .plot-card h3 {{ margin: 0 0 12px 0; font-size: 16px; }}
    .plot-card img {{ width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 8px; background: white; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <h1>{esc(title)}</h1>
  <p class="subtitle">Standalone SVG plots for the 20 representative TCGA lung patients. See <a href="index.html">index.html</a> for the full narrative report.</p>
  <div class="grid">
{gallery_items}
  </div>
</body>
</html>
"""
    (plots_dir.parent / "gallery.html").write_text(gallery)


def render_report(
    out_dir: Path,
    master_summary: list[dict[str, Any]],
    mutation_freq: list[dict[str, Any]],
    plot_svgs: dict[str, str],
) -> None:
    patient_rows = master_summary
    project_counts = count_values(patient_rows, "project_id")
    smoking_counts = count_values(patient_rows, "smoking_group")
    sex_counts = count_values(patient_rows, "sex")
    vital_counts = count_values(patient_rows, "vital_status")
    stage_counts = count_values(patient_rows, "ajcc_pathologic_stage")
    ages = [to_float(r.get("age_at_diagnosis_years")) for r in patient_rows]
    ages = [v for v in ages if v is not None]

    cards = [
        ("Representative patients", len(patient_rows)),
        ("LUAD patients", project_counts.get("TCGA-LUAD", 0)),
        ("LUSC patients", project_counts.get("TCGA-LUSC", 0)),
        ("Median age at diagnosis", fmt_num(median(ages), 1)),
        ("Deaths recorded", vital_counts.get("Dead", 0)),
        ("Total somatic mutations", sum(int(r.get("somatic_mutation_rows") or 0) for r in patient_rows)),
    ]
    card_html = "\n".join(
        f'<div class="card"><div class="card-value">{esc(v)}</div><div class="card-label">{esc(k)}</div></div>'
        for k, v in cards
    )

    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Representative 20 TCGA Lung Patients — Visual Summary</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 28px; color: #0f172a; background: #f8fafc; }}
    h1, h2, h3 {{ color: #0f172a; }}
    .subtitle {{ color: #475569; max-width: 980px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 22px 0; }}
    .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }}
    .card-value {{ font-size: 28px; font-weight: 700; }}
    .card-label {{ color: #64748b; margin-top: 4px; }}
    .panel {{ background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin: 18px 0; overflow-x: auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; font-weight: 650; }}
    .chart-title {{ font-size: 18px; font-weight: 700; fill: #0f172a; }}
    .axis-label, .legend {{ font-size: 12px; fill: #475569; }}
    .value-label {{ font-size: 12px; fill: #0f172a; }}
    .note {{ color: #475569; font-size: 14px; }}
    code {{ background: #e2e8f0; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Representative 20 TCGA Lung Patients — Visual Summary</h1>
  <p class="subtitle">
    Comprehensive visualization of clinical, mutation, RNA expression, RPPA proteomics, copy-number,
    miRNA, and treatment data for the stratified 20-patient cohort (10 LUAD + 10 LUSC; 5 smokers +
    5 lifelong non-smokers per histology). Somatic mutations are from whole-exome MAF files (SNVs/indels).
  </p>

  <div class="cards">{card_html}</div>

  <div class="panel">
    <h2>1. Cohort composition</h2>
    <div class="grid">
      <div>{plot_svgs.get("01_cohort_composition.svg", "")}</div>
      <div>{plot_svgs.get("02_histology_smoking_matrix.svg", "")}</div>
      <div>{histogram(ages, "Age at diagnosis distribution")}</div>
      <div>{bar_chart(project_counts, "Patients by TCGA project", color=COLORS["purple"])}</div>
    </div>
  </div>

  <div class="panel">
    <h2>2. Clinical demographics and outcomes</h2>
    <div class="grid">
      <div>{bar_chart(sex_counts, "Sex", color=COLORS["blue"])}</div>
      <div>{bar_chart(vital_counts, "Vital status", color=COLORS["red"])}</div>
      <div>{bar_chart(stage_counts, "AJCC pathologic stage", color=COLORS["purple"])}</div>
      <div>{bar_chart(smoking_counts, "Smoking group (selection stratum)", color=COLORS["gray"])}</div>
    </div>
  </div>

  <div class="panel">
    <h2>3. Data availability across modalities</h2>
    <p class="note">Heatmap shows which data layers are present for each patient. RPPA is missing for 6/20 patients; miRNA for 2/20.</p>
    {plot_svgs.get("03_data_availability_heatmap.svg", "")}
    {table_html(master_summary, ["case_submitter_id", "project_id", "smoking_group", "somatic_mutation_rows", "genome_wide_rna_rows", "rppa_protein_rows", "cnv_segments", "mirna_targets", "methylation_files", "slide_count"], limit=20)}
  </div>

  <div class="panel">
    <h2>4. Somatic mutation landscape</h2>
    <p class="note">Mutation burden and driver-gene alterations from masked somatic MAF files (whole-exome, not whole-genome).</p>
    <div class="grid">
      <div>{plot_svgs.get("04_mutation_burden_by_patient.svg", "")}</div>
      <div>{plot_svgs.get("05_variant_classification_cohort.svg", "")}</div>
    </div>
    {plot_svgs.get("06_driver_gene_mutation_matrix.svg", "")}
    {grouped_mutation_chart(mutation_freq, "Important-gene mutation frequency in the 20-patient cohort")}
    <h3>Driver mutation frequencies</h3>
    {table_html(mutation_freq, ["gene", "mutated_cases", "analyzable_cases", "overall_pct", "luad_mutated", "luad_total", "luad_pct", "lusc_mutated", "lusc_total", "lusc_pct"], limit=20)}
    {plot_svgs.get("07_chromosome_mutation_landscape.svg", "")}
  </div>

  <div class="panel">
    <h2>5. RNA expression (important genes)</h2>
    <p class="note">TPM (transcripts per million) for 30 curated lung driver genes. Color intensity reflects log-scaled expression.</p>
    {plot_svgs.get("08_important_gene_rna_heatmap.svg", "")}
  </div>

  <div class="panel">
    <h2>6. Copy-number and miRNA summaries</h2>
    <div class="grid">
      <div>{plot_svgs.get("09_cnv_alteration_burden.svg", "")}</div>
      <div>{plot_svgs.get("10_mirna_coverage.svg", "")}</div>
    </div>
  </div>

  <div class="panel">
    <h2>7. Treatment history and resistance proxies</h2>
    <div class="grid">
      <div>{bar_chart(yes_no_field_counts(patient_rows, "prior_treatment", title_yes="Prior treatment reported", title_no="No prior treatment", title_missing="Not reported"), "Prior treatment", color=COLORS["blue"])}</div>
      <div>{bar_chart(split_field_counts(patient_rows, "treatment_types"), "Treatment types", color=COLORS["purple"], max_items=10)}</div>
      <div>{bar_chart(count_values(patient_rows, "disease_response"), "Disease response", color=COLORS["gray"])}</div>
      <div>{bar_chart(count_values(patient_rows, "progression_or_recurrence"), "Progression or recurrence", color=COLORS["red"])}</div>
      <div>{bar_chart(resistance_proxy_counts(patient_rows), "Resistance proxies", color=COLORS["red"])}</div>
    </div>
  </div>

  <div class="panel">
    <h2>8. Master patient summary</h2>
    <p class="note">Full table: <code>master_patient_summary.csv</code>. Per-patient bundles live under <code>data_package/per_patient/</code>.</p>
    {table_html(master_summary, ["case_submitter_id", "project_id", "smoking_group", "age_at_diagnosis_years", "ajcc_pathologic_stage", "vital_status", "survival_time_days", "important_gene_mutations", "somatic_mutation_rows", "prior_treatment", "disease_response"], limit=20)}
  </div>

  <div class="panel">
    <h2>Generated files</h2>
    <ul>
      <li><code>index.html</code> — this report</li>
      <li><code>gallery.html</code> — standalone plot gallery</li>
      <li><code>master_patient_summary.csv</code> — one row per patient with all key metrics</li>
      <li><code>driver_gene_mutation_matrix.csv</code> — patient × gene mutation counts</li>
      <li><code>per_patient_molecular_summary.csv</code> — mutation burden and modality row counts</li>
      <li><code>per_patient_cnv_summary.csv</code> — CNV segment and alteration counts</li>
      <li><code>cohort_visual_summary.json</code> — report-level counts</li>
      <li><code>plots/</code> — individual SVG charts</li>
    </ul>
  </div>
</body>
</html>
"""
    (out_dir / "index.html").write_text(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument(
        "--rep-dir",
        type=Path,
        default=root / "representative_patients",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "representative_patients" / "visual_report",
    )
    args = parser.parse_args()

    rep_dir = args.rep_dir
    pkg_dir = rep_dir / "data_package"
    gen_dir = rep_dir / "genomic_data"
    out_dir = args.out_dir
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    selection = read_csv(rep_dir / "representative_20_patients.csv")
    clinical = read_csv(pkg_dir / "clinical" / "clinical_metadata.csv")
    data_avail = read_csv(pkg_dir / "data_availability_summary.csv")
    genomic_avail = read_csv(gen_dir / "genomic_availability_summary.csv")
    important_mut = read_csv(pkg_dir / "important_gene_mutations.csv")
    somatic = read_csv(pkg_dir / "somatic_mutations.csv")
    rna = read_csv(pkg_dir / "important_gene_expression.csv")
    variant_class = read_csv(gen_dir / "mutation_maps" / "variant_classification_summary.csv")
    by_chrom = read_csv(gen_dir / "mutation_maps" / "mutations_by_chromosome.csv")
    cnv_rows = read_csv(gen_dir / "parsed_tables" / "copy_number_segments.csv")
    mirna_rows = read_csv(gen_dir / "parsed_tables" / "mirna_expression.csv")

    patient_meta = {r["case_submitter_id"]: r for r in selection}
    patients_sorted = sorted(patient_meta, key=lambda p: (
        patient_meta[p].get("project_id", ""),
        patient_meta[p].get("smoking_group", ""),
        p,
    ))

    mutation_freq = build_mutation_frequency(important_mut, patient_meta)
    mutation_burden = per_patient_mutation_burden(somatic, data_avail)
    cnv_summary = per_patient_cnv_summary(cnv_rows)
    mirna_summary = per_patient_mirna_summary(mirna_rows)
    master_summary = build_master_patient_summary(
        selection, clinical, data_avail, genomic_avail, mutation_burden, cnv_summary, mirna_summary
    )

    driver_genes, driver_matrix = build_driver_mutation_matrix(important_mut, patients_sorted)
    avail_patients, avail_layers, avail_values = build_data_availability_matrix(clinical, data_avail, genomic_avail)
    rna_patients, rna_genes, rna_values = rna_expression_heatmap(rna, patients_sorted)

    # Cohort composition stacked bar
    luad_smoker = sum(1 for r in selection if r.get("project_id") == "TCGA-LUAD" and r.get("smoking_group") == "smoker")
    luad_non = sum(1 for r in selection if r.get("project_id") == "TCGA-LUAD" and r.get("smoking_group") == "non_smoker")
    lusc_smoker = sum(1 for r in selection if r.get("project_id") == "TCGA-LUSC" and r.get("smoking_group") == "smoker")
    lusc_non = sum(1 for r in selection if r.get("project_id") == "TCGA-LUSC" and r.get("smoking_group") == "non_smoker")

    plot_specs: list[tuple[str, str]] = [
        (
            "01_cohort_composition.svg",
            stacked_bar_chart(
                ["LUAD", "LUSC"],
                {"Smoker": [luad_smoker, lusc_smoker], "Non-smoker": [luad_non, lusc_non]},
                "Cohort composition: histology × smoking status",
                colors=[COLORS["orange"], COLORS["blue"]],
            ),
        ),
        (
            "02_histology_smoking_matrix.svg",
            binary_matrix_heatmap(
                ["LUAD smoker", "LUAD non-smoker", "LUSC smoker", "LUSC non-smoker"],
                ["Patients selected"],
                {
                    ("LUAD smoker", "Patients selected"): luad_smoker,
                    ("LUAD non-smoker", "Patients selected"): luad_non,
                    ("LUSC smoker", "Patients selected"): lusc_smoker,
                    ("LUSC non-smoker", "Patients selected"): lusc_non,
                },
                "Selection strata coverage (target: 5 per cell)",
                width=420,
                cell=40,
                row_label_w=140,
                col_label_h=40,
                color_on=COLORS["green"],
            ),
        ),
        (
            "03_data_availability_heatmap.svg",
            binary_matrix_heatmap(
                [p.replace("TCGA-", "") for p in avail_patients],
                avail_layers,
                {(p.replace("TCGA-", ""), layer): avail_values.get((p, layer), 0) for p in avail_patients for layer in avail_layers},
                "Data modality availability by patient",
                width=980,
                cell=16,
                row_label_w=70,
                col_label_h=100,
            ),
        ),
        (
            "04_mutation_burden_by_patient.svg",
            horizontal_bar_chart(
                [r["case_submitter_id"].replace("TCGA-", "") for r in mutation_burden],
                [float(r["somatic_mutation_rows"]) for r in mutation_burden],
                "Somatic mutation burden by patient (MAF rows)",
                color=COLORS["red"],
                x_label="MAF mutation rows",
            ),
        ),
        (
            "05_variant_classification_cohort.svg",
            bar_chart(
                Counter(
                    row["variant_classification"]
                    for row in variant_class
                    if row.get("variant_classification")
                ),
                "Variant classifications across cohort",
                color=COLORS["purple"],
                max_items=15,
            ),
        ),
        (
            "06_driver_gene_mutation_matrix.svg",
            binary_matrix_heatmap(
                [p.replace("TCGA-", "") for p in patients_sorted],
                driver_genes[:25],
                {
                    (p.replace("TCGA-", ""), g): 1 if driver_matrix.get((p, g), 0) else 0
                    for p in patients_sorted
                    for g in driver_genes[:25]
                },
                "Important driver-gene mutations by patient",
                width=980,
                cell=14,
                row_label_w=70,
                col_label_h=100,
                color_on=COLORS["red"],
            ),
        ),
        (
            "07_chromosome_mutation_landscape.svg",
            chromosome_landscape_chart(
                {
                    patient: Counter(
                        {
                            row["chromosome"]: int(row["mutation_count"])
                            for row in by_chrom
                            if row.get("case_submitter_id") == patient
                        }
                    )
                    for patient in patients_sorted
                },
                "Genome-wide mutation counts by chromosome",
            ),
        ),
        (
            "08_important_gene_rna_heatmap.svg",
            binary_matrix_heatmap(
                [p.replace("TCGA-", "") for p in rna_patients],
                rna_genes[:20],
                {
                    (p.replace("TCGA-", ""), g): rna_values.get((p, g), 0)
                    for p in rna_patients
                    for g in rna_genes[:20]
                },
                "Important-gene RNA expression (log-scaled TPM intensity)",
                width=980,
                cell=14,
                row_label_w=70,
                col_label_h=100,
                color_on=COLORS["green"],
                color_scale=("#dcfce7", "#4ade80", "#15803d"),
                show_legend=True,
            ),
        ),
        (
            "09_cnv_alteration_burden.svg",
            stacked_bar_chart(
                [r["case_submitter_id"].replace("TCGA-", "") for r in cnv_summary],
                {
                    "Amplification (CN≥3)": [r["amp"] for r in cnv_summary],
                    "Deletion (CN≤1)": [r["del"] for r in cnv_summary],
                    "Neutral (CN=2)": [r["neutral"] for r in cnv_summary],
                },
                "Copy-number segment classes by patient",
                width=980,
                height=420,
                colors=[COLORS["red"], COLORS["blue"], COLORS["light_gray"]],
            ),
        ),
        (
            "10_mirna_coverage.svg",
            horizontal_bar_chart(
                [r["case_submitter_id"].replace("TCGA-", "") for r in mirna_summary],
                [float(r["mirna_targets"]) for r in mirna_summary],
                "miRNA targets quantified by patient",
                color=COLORS["purple"],
                x_label="miRNA features",
            ),
        ),
    ]

    written: list[str] = []
    plot_svgs: dict[str, str] = {}
    for filename, svg in plot_specs:
        path = plots_dir / filename
        write_svg(path, svg)
        written.append(filename)
        plot_svgs[filename] = svg

    render_gallery(plots_dir, written, "Representative 20 Patients — Plot Gallery")
    render_report(out_dir, master_summary, mutation_freq, plot_svgs)

    # Summary tables
    master_fields = list(master_summary[0].keys()) if master_summary else []
    write_csv(out_dir / "master_patient_summary.csv", master_summary, master_fields)
    write_csv(out_dir / "per_patient_molecular_summary.csv", mutation_burden, list(mutation_burden[0].keys()) if mutation_burden else [])
    write_csv(out_dir / "per_patient_cnv_summary.csv", cnv_summary, list(cnv_summary[0].keys()) if cnv_summary else [])
    write_csv(out_dir / "per_patient_mirna_summary.csv", mirna_summary, list(mirna_summary[0].keys()) if mirna_summary else [])

    matrix_rows = []
    for p in patients_sorted:
        for g in driver_genes:
            matrix_rows.append(
                {
                    "case_submitter_id": p,
                    "gene": g,
                    "mutation_count": driver_matrix.get((p, g), 0),
                    "mutated": 1 if driver_matrix.get((p, g), 0) else 0,
                }
            )
    write_csv(out_dir / "driver_gene_mutation_matrix.csv", matrix_rows, ["case_submitter_id", "gene", "mutation_count", "mutated"])

    mutation_freq_fields = [
        "gene", "mutated_cases", "analyzable_cases", "overall_pct",
        "luad_mutated", "luad_total", "luad_pct", "lusc_mutated", "lusc_total", "lusc_pct",
    ]
    write_csv(out_dir / "driver_mutation_frequency.csv", mutation_freq, mutation_freq_fields)

    cohort_summary = {
        "patient_count": len(master_summary),
        "project_counts": dict(count_values(master_summary, "project_id")),
        "smoking_group_counts": dict(count_values(master_summary, "smoking_group")),
        "vital_status_counts": dict(count_values(master_summary, "vital_status")),
        "total_somatic_mutations": sum(int(r.get("somatic_mutation_rows") or 0) for r in master_summary),
        "patients_with_rppa": sum(1 for r in master_summary if int(float(r.get("rppa_protein_rows") or 0)) > 0),
        "patients_with_mirna": sum(1 for r in master_summary if int(float(r.get("mirna_targets") or 0)) > 0),
        "patients_with_methylation": sum(1 for r in master_summary if int(float(r.get("methylation_files") or 0)) > 0),
        "median_mutation_burden": statistics.median([int(r.get("somatic_mutation_rows") or 0) for r in master_summary]),
        "treatment_summary": build_treatment_summary(clinical),
        "plot_files": written,
        "method_notes": [
            "20-patient stratified cohort: 10 LUAD + 10 LUSC, 5 smokers + 5 non-smokers per histology.",
            "Somatic mutations from TCGA masked MAF (whole-exome SNVs/indels).",
            "CNV from ASCAT2 allele-specific segment files.",
            "RNA expression TPM for 30 curated important lung genes.",
        ],
    }
    write_json(out_dir / "cohort_visual_summary.json", cohort_summary)

    print(f"Wrote visual report to {out_dir}")
    print(f"  Patients summarized: {len(master_summary)}")
    print(f"  Plots: {len(written)}")
    print(f"  Open: {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
