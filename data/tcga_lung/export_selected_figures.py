#!/usr/bin/env python3
"""Export selected PowerPoint slides as standalone PNG and SVG figures."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Slide numbers the user requested mapped to export stems.
SELECTED_SLIDES: dict[int, str] = {
    5: "slide05_age_at_diagnosis_distribution",
    7: "slide07_vital_status",
    8: "slide08_sex_distribution",
    9: "slide09_ajcc_pathologic_stage",
    14: "slide14_top_driver_gene_mutation_frequency",
    17: "slide17_variant_classification_cohort_wide",
    22: "slide22_treatment_types_patient_mentions",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value: Any, digits: int = 1) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "0%"


def count_field(rows: list[dict[str, str]], field: str, missing: str = "missing") -> Counter[str]:
    c: Counter[str] = Counter()
    for row in rows:
        c[row.get(field) or missing] += 1
    return c


def age_histogram_bins(ages: list[float], bins: int = 8) -> tuple[list[str], list[int]]:
    if not ages:
        return [], []
    lo, hi = min(ages), max(ages)
    if lo == hi:
        hi = lo + 1
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    counts = [0] * bins
    for age in ages:
        idx = min(bins - 1, int((age - lo) / (hi - lo) * bins))
        counts[idx] += 1
    labels = [f"{edges[i]:.0f}-{edges[i + 1]:.0f}" for i in range(bins)]
    return labels, counts


def aggregate_variant_classes(variant_rows: list[dict[str, str]]) -> Counter[str]:
    c: Counter[str] = Counter()
    for row in variant_rows:
        cls = row.get("variant_classification", "")
        count = int(float(row.get("mutation_count") or 0))
        if cls:
            c[cls] += count
    return c


def save_figure(fig: plt.Figure, out_dir: Path, stem: str) -> list[str]:
    written: list[str] = []
    for ext in ("png", "svg"):
        path = out_dir / f"{stem}.{ext}"
        fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        written.append(path.name)
    plt.close(fig)
    return written


def add_stats_box(fig: plt.Figure, lines: list[str]) -> None:
    text = "\n".join(lines)
    fig.text(
        0.98,
        0.02,
        text,
        ha="right",
        va="bottom",
        fontsize=9,
        color="#475569",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f8fafc", edgecolor="#e2e8f0"),
        family="sans-serif",
    )


def export_slide05_age(patients: list[dict[str, str]], out_dir: Path) -> list[str]:
    n = len(patients)
    ages = [v for v in (to_float(r.get("age_at_diagnosis_years")) for r in patients) if v is not None]
    labels, counts = age_histogram_bins(ages)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(labels, counts, color="#16a34a", edgecolor="white")
    ax.set_title("Age at diagnosis distribution", fontsize=16, fontweight="bold", color="#0f172a")
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Patients")
    ax.tick_params(axis="x", rotation=35)
    add_stats_box(
        fig,
        [
            f"Mean age: {fmt_num(statistics.mean(ages))} years",
            f"Median age: {fmt_num(statistics.median(ages))} years",
            f"Range: {fmt_num(min(ages))} – {fmt_num(max(ages))} years",
            f"Patients with age data: {len(ages)}/{n}",
        ],
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[5])


def export_slide07_vital(patients: list[dict[str, str]], out_dir: Path) -> list[str]:
    n = len(patients)
    vital = count_field(patients, "vital_status")
    labels = ["Alive", "Dead"]
    values = [vital.get("Alive", 0), vital.get("Dead", 0)]
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#3b82f6", "#dc2626"]
    wedges, _, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors,
        startangle=90,
        textprops={"fontsize": 11},
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.set_title("Vital status", fontsize=16, fontweight="bold", color="#0f172a")
    events = sum(int(float(r.get("survival_event") or 0)) for r in patients)
    add_stats_box(
        fig,
        [
            f"Alive: {values[0]} ({pct(values[0], n)})",
            f"Dead: {values[1]} ({pct(values[1], n)})",
            f"Death rate: {pct(values[1], n)}",
            f"Survival events: {events}",
        ],
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[7])


def export_slide08_sex(patients: list[dict[str, str]], out_dir: Path) -> list[str]:
    n = len(patients)
    sex = count_field(patients, "sex")
    labels, values = zip(*sex.most_common()) if sex else ([], [])
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 11})
    ax.set_title("Sex distribution", fontsize=16, fontweight="bold", color="#0f172a")
    add_stats_box(fig, [f"{label}: {int(v)} ({pct(int(v), n)})" for label, v in zip(labels, values)])
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[8])


def export_slide09_stage(patients: list[dict[str, str]], out_dir: Path) -> list[str]:
    stage = count_field(patients, "ajcc_pathologic_stage")
    items = stage.most_common()
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    early = sum(v for k, v in stage.items() if "Stage I" in k and "Stage III" not in k)
    advanced = sum(v for k, v in stage.items() if "Stage III" in k or "Stage IV" in k)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(labels, values, color="#7c3aed", edgecolor="white")
    ax.set_title("AJCC pathologic stage", fontsize=16, fontweight="bold", color="#0f172a")
    ax.set_ylabel("Patients")
    ax.tick_params(axis="x", rotation=30)
    add_stats_box(
        fig,
        [
            f"Most common: {items[0][0]} (n={items[0][1]})" if items else "",
            f"Early stage (I–II): {early}",
            f"Advanced stage (III–IV): {advanced}",
        ],
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[9])


def export_slide14_drivers(driver_freq: list[dict[str, str]], n: int, summary: dict, out_dir: Path) -> list[str]:
    top = driver_freq[:12]
    genes = [r["gene"] for r in top]
    pcts = [float(r["overall_pct"]) for r in top]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(genes, pcts, color="#3b82f6", edgecolor="white")
    ax.set_title("Top driver-gene mutation frequency", fontsize=16, fontweight="bold", color="#0f172a")
    ax.set_ylabel("Mutated patients (%)")
    ax.tick_params(axis="x", rotation=45)
    add_stats_box(
        fig,
        [
            f"TP53: {driver_freq[0]['mutated_cases']}/{n} ({driver_freq[0]['overall_pct']}%)",
            f"Drivers tracked: {len(driver_freq)}",
            f"Median burden: {fmt_num(summary.get('median_mutation_burden', 0), 0)} MAF rows/patient",
            "Whole-exome MAF (SNVs/indels)",
        ],
    )
    fig.tight_layout(rect=[0, 0.1, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[14])


def export_slide17_variants(variant_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    variant_counts = aggregate_variant_classes(variant_rows)
    items = variant_counts.most_common(8)
    labels = [k.replace("_", " ") for k, _ in items]
    values = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 9})
    ax.set_title("Variant classification (cohort-wide)", fontsize=16, fontweight="bold", color="#0f172a")
    add_stats_box(
        fig,
        [
            f"Total classified: {sum(variant_counts.values()):,}",
            f"Missense: {variant_counts.get('Missense_Mutation', 0):,}",
            f"Silent: {variant_counts.get('Silent', 0):,}",
            f"Nonsense: {variant_counts.get('Nonsense_Mutation', 0):,}",
        ],
    )
    fig.tight_layout(rect=[0, 0.1, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[17])


def export_slide22_treatment(summary: dict, n: int, out_dir: Path) -> list[str]:
    treat = summary.get("treatment_summary", {})
    top_types = treat.get("top_treatment_types", {})
    items = sorted(top_types.items(), key=lambda kv: -kv[1])[:8]
    labels = [k if len(k) <= 32 else k[:29] + "..." for k, _ in items]
    values = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels[::-1], values[::-1], color="#7c3aed", edgecolor="white")
    ax.set_title("Treatment types (patient mentions)", fontsize=16, fontweight="bold", color="#0f172a")
    ax.set_xlabel("Mentions")
    cov = treat.get("field_coverage", {}).get("treatment_types", 0)
    cov_pct = treat.get("field_coverage_pct", {}).get("treatment_types", 0)
    add_stats_box(
        fig,
        [
            f"Patients with treatment types: {cov}/{n}",
            f"Field coverage: {cov_pct}%",
        ],
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    return save_figure(fig, out_dir, SELECTED_SLIDES[22])


def build_manifest(files: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_powerpoint": "Representative_20_Patients_Summary.pptx",
        "selected_slides": list(SELECTED_SLIDES.keys()),
        "figures": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=root / "representative_patients" / "visual_report",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "representative_patients" / "visual_report" / "selected figures",
    )
    args = parser.parse_args()

    report_dir = args.report_dir
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = json.loads((report_dir / "cohort_visual_summary.json").read_text())
    patients = read_csv(report_dir / "master_patient_summary.csv")
    driver_freq = read_csv(report_dir / "driver_mutation_frequency.csv")
    gen_dir = report_dir.parent / "genomic_data"
    variant_rows = read_csv(gen_dir / "mutation_maps" / "variant_classification_summary.csv")
    n = len(patients)

    manifest_entries: list[dict[str, Any]] = []
    exporters = [
        (5, "Age at diagnosis distribution", export_slide05_age(patients, out_dir)),
        (7, "Vital status", export_slide07_vital(patients, out_dir)),
        (8, "Sex distribution", export_slide08_sex(patients, out_dir)),
        (9, "AJCC pathologic stage", export_slide09_stage(patients, out_dir)),
        (14, "Top driver-gene mutation frequency", export_slide14_drivers(driver_freq, n, summary, out_dir)),
        (17, "Variant classification (cohort-wide)", export_slide17_variants(variant_rows, out_dir)),
        (22, "Treatment types (patient mentions)", export_slide22_treatment(summary, n, out_dir)),
    ]
    for slide_num, title, written in exporters:
        manifest_entries.append(
            {
                "slide_number": slide_num,
                "title": title,
                "stem": SELECTED_SLIDES[slide_num],
                "files": written,
            }
        )

    manifest = build_manifest(manifest_entries)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    readme = """# Selected figures

Standalone exports of selected slides from `Representative_20_Patients_Summary.pptx`.

| Slide | Title | PNG | SVG |
|------:|-------|-----|-----|
"""
    for entry in manifest_entries:
        stem = entry["stem"]
        readme += f"| {entry['slide_number']} | {entry['title']} | `{stem}.png` | `{stem}.svg` |\n"

    readme += """
Each figure includes summary statistics matching the PowerPoint slide.

Regenerate:

```bash
python3 data/tcga_lung/export_selected_figures.py
```
"""
    (out_dir / "README.md").write_text(readme)

    print(f"Wrote {len(manifest_entries)} figures to {out_dir}")
    for entry in manifest_entries:
        print(f"  Slide {entry['slide_number']}: {', '.join(entry['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
