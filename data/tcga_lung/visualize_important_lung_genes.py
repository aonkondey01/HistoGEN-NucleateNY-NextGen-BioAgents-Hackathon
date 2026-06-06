#!/usr/bin/env python3
"""Build a self-contained visual report for important TCGA lung genes.

The report is intentionally dependency-free: it uses only Python's standard
library and writes inline SVG charts plus CSV summary tables. It summarizes:

* cohort size and clinical demographics,
* important LUAD/LUSC mutation frequencies,
* clinical differences by driver-gene mutation status, and
* exploratory survival associations for mutations, RNA expression, and RPPA
  protein expression.

The survival analyses are exploratory. They use median splits for expression
and protein values and a two-group log-rank test approximation. They are meant
to help prioritize visual review, not to replace a full statistical model.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

PROJECT_LABELS = {
    "TCGA-LUAD": "Lung adenocarcinoma",
    "TCGA-LUSC": "Lung squamous cell carcinoma",
}

MUTATION_DRIVER_ORDER = [
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

COLORS = {
    "blue": "#3b82f6",
    "orange": "#f97316",
    "green": "#16a34a",
    "purple": "#7c3aed",
    "red": "#dc2626",
    "gray": "#64748b",
    "light_gray": "#e2e8f0",
    "dark": "#0f172a",
}

SIGNIFICANCE_ALPHA = 0.05


def is_significant(row: dict[str, Any], *, alpha: float = SIGNIFICANCE_ALPHA) -> bool:
    p = to_float(row.get("logrank_p_value"))
    return p is not None and p < alpha


def significant_survival_rows(rows: list[dict[str, Any]], *, alpha: float = SIGNIFICANCE_ALPHA) -> list[dict[str, Any]]:
    return [row for row in rows if is_significant(row, alpha=alpha)]


def km_curves_html(
    rows: list[dict[str, Any]],
    plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
    *,
    key_field: str,
    group_a_label: str,
    group_b_label: str,
    title_prefix: str,
    alpha: float = SIGNIFICANCE_ALPHA,
) -> str:
    sig_rows = significant_survival_rows(rows, alpha=alpha)
    if not sig_rows:
        return f"<p>No significant Kaplan-Meier curves at p &lt; {alpha}.</p>"
    parts = ['<div class="grid">']
    for row in sig_rows:
        key = row[key_field]
        if key not in plot_groups:
            continue
        parts.append(
            "<div>"
            + km_curve(
                *plot_groups[key],
                title=f"{title_prefix}: {key}",
                group_a_label=group_a_label,
                group_b_label=group_b_label,
                p_value=to_float(row.get("logrank_p_value")),
            )
            + "</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


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


def median(values: Iterable[float]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return statistics.median(vals) if vals else None


def percentile(values: list[float], p: float) -> float | None:
    vals = sorted(values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - idx) + vals[hi] * (idx - lo)


def fmt_num(value: Any, digits: int = 2) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return f"{value:.{digits}f}"
    return str(value)


def numeric_patient_survival(patients: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for case_id, row in patients.items():
        time = to_float(row.get("survival_time_days"))
        event = to_float(row.get("survival_event"))
        if time is None or event is None or time <= 0:
            continue
        out[case_id] = {"time": time, "event": 1.0 if event >= 1 else 0.0}
    return out


def count_values(rows: Iterable[dict[str, str]], field: str, missing: str = "missing") -> Counter[str]:
    c: Counter[str] = Counter()
    for row in rows:
        val = row.get(field) or missing
        c[val] += 1
    return c


def bar_chart(
    counts: Counter[str] | dict[str, int],
    title: str,
    *,
    width: int = 840,
    bar_height: int = 24,
    color: str = COLORS["blue"],
    max_items: int = 20,
) -> str:
    items = [(k, int(v)) for k, v in counts.items()]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    items = items[:max_items]
    left = 210
    right = 90
    top = 54
    row_gap = 10
    height = top + len(items) * (bar_height + row_gap) + 30
    max_count = max([v for _, v in items] or [1])
    bar_width = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
    ]
    for i, (label, count) in enumerate(items):
        y = top + i * (bar_height + row_gap)
        w = max(1, bar_width * count / max_count)
        parts.append(f'<text x="0" y="{y + 17}" class="axis-label">{esc(label)}</text>')
        parts.append(
            f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_height}" rx="4" fill="{color}"></rect>'
        )
        parts.append(
            f'<text x="{left + w + 8:.1f}" y="{y + 17}" class="value-label">{count}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def grouped_mutation_chart(rows: list[dict[str, Any]], title: str, width: int = 920) -> str:
    top = 58
    left = 120
    right = 90
    row_h = 28
    gap = 12
    genes = [row["gene"] for row in rows[:20]]
    height = top + len(genes) * (row_h + gap) + 60
    max_pct = max([max(row["luad_pct"], row["lusc_pct"]) for row in rows[:20]] or [1])
    max_pct = max(max_pct, 1)
    scale_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
        f'<rect x="{left}" y="36" width="16" height="10" fill="{COLORS["blue"]}"></rect>',
        f'<text x="{left + 22}" y="45" class="legend">LUAD</text>',
        f'<rect x="{left + 90}" y="36" width="16" height="10" fill="{COLORS["orange"]}"></rect>',
        f'<text x="{left + 112}" y="45" class="legend">LUSC</text>',
    ]
    for i, row in enumerate(rows[:20]):
        y = top + i * (row_h + gap)
        luad_w = scale_w * row["luad_pct"] / max_pct
        lusc_w = scale_w * row["lusc_pct"] / max_pct
        parts.append(f'<text x="0" y="{y + 20}" class="axis-label">{esc(row["gene"])}</text>')
        parts.append(
            f'<rect x="{left}" y="{y}" width="{luad_w:.1f}" height="12" rx="3" fill="{COLORS["blue"]}"></rect>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 16}" width="{lusc_w:.1f}" height="12" rx="3" fill="{COLORS["orange"]}"></rect>'
        )
        parts.append(
            f'<text x="{left + max(luad_w, lusc_w) + 8:.1f}" y="{y + 20}" class="value-label">'
            f'{row["luad_mutated"]}/{row["luad_total"]} LUAD, {row["lusc_mutated"]}/{row["lusc_total"]} LUSC</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def histogram(values: list[float], title: str, bins: int = 12, width: int = 840, height: int = 300) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return f"<p>No numeric values for {esc(title)}.</p>"
    lo, hi = min(vals), max(vals)
    if lo == hi:
        hi = lo + 1
    counts = [0] * bins
    for val in vals:
        idx = min(bins - 1, int((val - lo) / (hi - lo) * bins))
        counts[idx] += 1
    max_count = max(counts) or 1
    left = 55
    bottom = 240
    chart_w = width - 90
    chart_h = 170
    bar_w = chart_w / bins - 4
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{left + chart_w}" y2="{bottom}" stroke="#94a3b8"></line>',
        f'<line x1="{left}" y1="{bottom - chart_h}" x2="{left}" y2="{bottom}" stroke="#94a3b8"></line>',
    ]
    for i, count in enumerate(counts):
        x = left + i * (chart_w / bins) + 2
        h = chart_h * count / max_count
        y = bottom - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{COLORS["green"]}"></rect>')
    parts.append(f'<text x="{left}" y="{bottom + 24}" class="axis-label">{fmt_num(lo, 1)}</text>')
    parts.append(f'<text x="{left + chart_w - 42}" y="{bottom + 24}" class="axis-label">{fmt_num(hi, 1)}</text>')
    parts.append(f'<text x="{left + chart_w / 2 - 45}" y="{bottom + 44}" class="axis-label">Age at diagnosis, years</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def format_p_value(p_value: float | None) -> str:
    if p_value is None:
        return "n/a"
    if p_value < 0.001:
        return f"{p_value:.2e}"
    return f"{p_value:.4f}"


def km_curve(
    group_a: list[dict[str, float]],
    group_b: list[dict[str, float]],
    title: str,
    *,
    group_a_label: str = "Group A",
    group_b_label: str = "Group B",
    p_value: float | None = None,
    width: int = 840,
    height: int = 360,
) -> str:
    def curve(group: list[dict[str, float]]) -> list[tuple[float, float]]:
        if not group:
            return [(0, 1)]
        times = sorted({row["time"] for row in group})
        survival = 1.0
        points = [(0.0, 1.0)]
        for t in times:
            at_risk = sum(1 for row in group if row["time"] >= t)
            events = sum(1 for row in group if row["time"] == t and row["event"] >= 1)
            if at_risk and events:
                survival *= 1.0 - events / at_risk
            points.append((t, survival))
        return points

    pts_a = curve(group_a)
    pts_b = curve(group_b)
    max_t = max([p[0] for p in pts_a + pts_b] or [1]) or 1
    left, top, chart_w, chart_h = 72, 72, width - 112, 210
    bottom = top + chart_h
    events_a = int(sum(r["event"] for r in group_a))
    events_b = int(sum(r["event"] for r in group_b))

    def path(points: list[tuple[float, float]]) -> str:
        d = []
        prev_x = left
        prev_y = bottom - chart_h
        d.append(f"M {prev_x:.1f} {prev_y:.1f}")
        for t, s in points[1:]:
            x = left + chart_w * t / max_t
            y = bottom - chart_h * s
            d.append(f"L {x:.1f} {prev_y:.1f}")
            d.append(f"L {x:.1f} {y:.1f}")
            prev_y = y
        return " ".join(d)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
        f'<text x="0" y="44" class="axis-label">Kaplan-Meier survival probability by follow-up time (days). Log-rank p = {esc(format_p_value(p_value))}.</text>',
        f'<rect x="{left}" y="{top}" width="{chart_w}" height="{chart_h}" fill="white" stroke="#cbd5e1"></rect>',
        f'<line x1="{left}" y1="{bottom}" x2="{left + chart_w}" y2="{bottom}" stroke="#94a3b8"></line>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#94a3b8"></line>',
        f'<path d="{path(pts_a)}" fill="none" stroke="{COLORS["blue"]}" stroke-width="3"></path>',
        f'<path d="{path(pts_b)}" fill="none" stroke="{COLORS["orange"]}" stroke-width="3"></path>',
        f'<text x="{left}" y="{bottom + 24}" class="axis-label">0</text>',
        f'<text x="{left + chart_w - 70}" y="{bottom + 24}" class="axis-label">{fmt_num(max_t, 0)}</text>',
        f'<text x="{left + chart_w / 2 - 70}" y="{bottom + 44}" class="axis-label">Follow-up time (days)</text>',
        f'<text x="8" y="{top + chart_h / 2 + 40}" class="axis-label" transform="rotate(-90 8 {top + chart_h / 2 + 40})">Survival probability</text>',
        f'<text x="{left - 8}" y="{top + 8}" class="axis-label" text-anchor="end">1.0</text>',
        f'<text x="{left - 8}" y="{bottom}" class="axis-label" text-anchor="end">0.0</text>',
        f'<rect x="{left + 8}" y="{top + 12}" width="14" height="10" fill="{COLORS["blue"]}"></rect>',
        f'<text x="{left + 28}" y="{top + 22}" class="legend">{esc(group_a_label)}, n={len(group_a)}, events={events_a}</text>',
        f'<rect x="{left + 8}" y="{top + 30}" width="14" height="10" fill="{COLORS["orange"]}"></rect>',
        f'<text x="{left + 28}" y="{top + 40}" class="legend">{esc(group_b_label)}, n={len(group_b)}, events={events_b}</text>',
        "</svg>",
    ]
    return "\n".join(parts)


def logrank(group_a: list[dict[str, float]], group_b: list[dict[str, float]]) -> dict[str, float | None]:
    if not group_a or not group_b:
        return {"chi_square": None, "p_value": None}
    event_times = sorted({r["time"] for r in group_a + group_b if r["event"] >= 1})
    observed = expected = variance = 0.0
    for t in event_times:
        n1 = sum(1 for r in group_a if r["time"] >= t)
        n2 = sum(1 for r in group_b if r["time"] >= t)
        d1 = sum(1 for r in group_a if r["time"] == t and r["event"] >= 1)
        d2 = sum(1 for r in group_b if r["time"] == t and r["event"] >= 1)
        n = n1 + n2
        d = d1 + d2
        if n <= 1 or d == 0:
            continue
        observed += d1
        expected += d * n1 / n
        variance += n1 * n2 * d * (n - d) / (n * n * (n - 1))
    if variance <= 0:
        return {"chi_square": None, "p_value": None}
    chi_square = (observed - expected) ** 2 / variance
    p_value = math.erfc(math.sqrt(chi_square / 2.0))
    return {"chi_square": chi_square, "p_value": p_value}


def median_survival(group: list[dict[str, float]]) -> float | None:
    if not group:
        return None
    points: list[tuple[float, float]] = []
    survival = 1.0
    for t in sorted({row["time"] for row in group}):
        at_risk = sum(1 for row in group if row["time"] >= t)
        events = sum(1 for row in group if row["time"] == t and row["event"] >= 1)
        if at_risk and events:
            survival *= 1.0 - events / at_risk
            points.append((t, survival))
            if survival <= 0.5:
                return t
    return None


def build_mutation_status(
    mutations: list[dict[str, str]],
    patients: dict[str, dict[str, str]],
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    analyzable_cases = {
        case_id
        for case_id, row in patients.items()
        if int(float(row.get("mutation_file_count") or 0)) > 0
    }
    mutated_by_gene: dict[str, set[str]] = defaultdict(set)
    for row in mutations:
        if row.get("case_id") in analyzable_cases:
            mutated_by_gene[row["gene"]].add(row["case_id"])

    totals_by_project = Counter(patients[c]["project_id"] for c in analyzable_cases)
    freq_rows: list[dict[str, Any]] = []
    genes = sorted(mutated_by_gene, key=lambda g: MUTATION_DRIVER_ORDER.index(g) if g in MUTATION_DRIVER_ORDER else 999)
    for gene in genes:
        cases = mutated_by_gene[gene]
        luad_cases = {c for c in cases if patients[c]["project_id"] == "TCGA-LUAD"}
        lusc_cases = {c for c in cases if patients[c]["project_id"] == "TCGA-LUSC"}
        total_mut = len(cases)
        total_analyzable = len(analyzable_cases)
        freq_rows.append(
            {
                "gene": gene,
                "mutated_cases": total_mut,
                "analyzable_cases": total_analyzable,
                "overall_pct": 100 * total_mut / total_analyzable if total_analyzable else 0,
                "luad_mutated": len(luad_cases),
                "luad_total": totals_by_project["TCGA-LUAD"],
                "luad_pct": 100 * len(luad_cases) / totals_by_project["TCGA-LUAD"] if totals_by_project["TCGA-LUAD"] else 0,
                "lusc_mutated": len(lusc_cases),
                "lusc_total": totals_by_project["TCGA-LUSC"],
                "lusc_pct": 100 * len(lusc_cases) / totals_by_project["TCGA-LUSC"] if totals_by_project["TCGA-LUSC"] else 0,
            }
        )
    freq_rows.sort(key=lambda r: (-r["mutated_cases"], r["gene"]))
    return mutated_by_gene, freq_rows


def clinical_by_mutation(
    patients: dict[str, dict[str, str]],
    mutated_by_gene: dict[str, set[str]],
) -> list[dict[str, Any]]:
    analyzable_cases = {
        case_id
        for case_id, row in patients.items()
        if int(float(row.get("mutation_file_count") or 0)) > 0
    }
    rows: list[dict[str, Any]] = []
    for gene, mutated_cases in sorted(mutated_by_gene.items()):
        wildtype_cases = analyzable_cases - mutated_cases
        for label, cases in [("mutated", mutated_cases), ("not_mutated", wildtype_cases)]:
            subset = [patients[c] for c in cases if c in patients]
            ages = [to_float(r.get("age_at_diagnosis_years")) for r in subset]
            ages = [v for v in ages if v is not None]
            survival = [to_float(r.get("survival_time_days")) for r in subset]
            survival = [v for v in survival if v is not None and v > 0]
            rows.append(
                {
                    "gene": gene,
                    "group": label,
                    "n": len(subset),
                    "median_age_at_diagnosis_years": median(ages),
                    "female": sum(1 for r in subset if r.get("sex") == "female"),
                    "male": sum(1 for r in subset if r.get("sex") == "male"),
                    "white": sum(1 for r in subset if r.get("race") == "white"),
                    "black_or_african_american": sum(1 for r in subset if r.get("race") == "black or african american"),
                    "asian": sum(1 for r in subset if r.get("race") == "asian"),
                    "alive": sum(1 for r in subset if r.get("vital_status") == "Alive"),
                    "dead": sum(1 for r in subset if r.get("vital_status") == "Dead"),
                    "median_survival_time_days_observed": median(survival),
                    "stage_i_or_ii": sum(1 for r in subset if "Stage I" in r.get("ajcc_pathologic_stage", "") or "Stage II" in r.get("ajcc_pathologic_stage", "")),
                    "stage_iii_or_iv": sum(1 for r in subset if "Stage III" in r.get("ajcc_pathologic_stage", "") or "Stage IV" in r.get("ajcc_pathologic_stage", "")),
                    "progression_or_recurrence_reported_yes": sum(1 for r in subset if "yes" in r.get("progression_or_recurrence", "").lower()),
                    "disease_response_values": "; ".join(sorted({r.get("disease_response") for r in subset if r.get("disease_response")})),
                }
            )
    return rows


def mutation_survival_associations(
    patients: dict[str, dict[str, str]],
    mutated_by_gene: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]]]:
    survival = numeric_patient_survival(patients)
    analyzable_cases = {
        case_id
        for case_id, row in patients.items()
        if int(float(row.get("mutation_file_count") or 0)) > 0 and case_id in survival
    }
    rows: list[dict[str, Any]] = []
    groups_for_plot: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]] = {}
    for gene, mutated_cases in mutated_by_gene.items():
        mut = [survival[c] for c in mutated_cases if c in analyzable_cases]
        wt = [survival[c] for c in analyzable_cases if c not in mutated_cases]
        if len(mut) < 10 or len(wt) < 10:
            continue
        stats = logrank(mut, wt)
        rows.append(
            {
                "gene": gene,
                "mutated_n": len(mut),
                "not_mutated_n": len(wt),
                "mutated_events": int(sum(r["event"] for r in mut)),
                "not_mutated_events": int(sum(r["event"] for r in wt)),
                "mutated_km_median_survival_days": median_survival(mut),
                "not_mutated_km_median_survival_days": median_survival(wt),
                "logrank_chi_square": stats["chi_square"],
                "logrank_p_value": stats["p_value"],
            }
        )
        groups_for_plot[gene] = (mut, wt)
    rows.sort(key=lambda r: (r["logrank_p_value"] if r["logrank_p_value"] is not None else 999, -r["mutated_n"]))
    return rows, groups_for_plot


def expression_matrix(rows: list[dict[str, str]], value_field: str, key_field: str = "gene") -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        case_id = row.get("case_id")
        key = row.get(key_field)
        val = to_float(row.get(value_field))
        if not case_id or not key or val is None:
            continue
        values[(case_id, key)].append(val)
    return {k: statistics.mean(v) for k, v in values.items() if v}


def median_split_survival_associations(
    patients: dict[str, dict[str, str]],
    values: dict[tuple[str, str], float],
    label_name: str,
    *,
    min_group: int = 30,
) -> tuple[list[dict[str, Any]], dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]]]:
    survival = numeric_patient_survival(patients)
    by_label: dict[str, dict[str, float]] = defaultdict(dict)
    for (case_id, label), value in values.items():
        if case_id in survival:
            by_label[label][case_id] = value
    rows: list[dict[str, Any]] = []
    groups_for_plot: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]] = {}
    for label, case_values in by_label.items():
        vals = list(case_values.values())
        cutoff = median(vals)
        if cutoff is None:
            continue
        low_cases = [c for c, v in case_values.items() if v <= cutoff]
        high_cases = [c for c, v in case_values.items() if v > cutoff]
        if len(low_cases) < min_group or len(high_cases) < min_group:
            continue
        low = [survival[c] for c in low_cases]
        high = [survival[c] for c in high_cases]
        stats = logrank(high, low)
        rows.append(
            {
                label_name: label,
                "median_split_cutoff": cutoff,
                "high_n": len(high),
                "low_n": len(low),
                "high_events": int(sum(r["event"] for r in high)),
                "low_events": int(sum(r["event"] for r in low)),
                "high_km_median_survival_days": median_survival(high),
                "low_km_median_survival_days": median_survival(low),
                "logrank_chi_square": stats["chi_square"],
                "logrank_p_value": stats["p_value"],
            }
        )
        groups_for_plot[label] = (high, low)
    rows.sort(key=lambda r: (r["logrank_p_value"] if r["logrank_p_value"] is not None else 999, r[label_name]))
    return rows, groups_for_plot


def write_svg(path: Path, svg: str) -> None:
    path.write_text(svg if svg.lstrip().startswith("<?xml") else svg)


def clinical_comparison_chart(
    clinical_rows: list[dict[str, Any]],
    title: str,
    metric: str,
    *,
    genes: list[str] | None = None,
    width: int = 920,
) -> str:
    """Grouped bar chart comparing mutated vs not-mutated clinical metrics."""
    by_gene: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in clinical_rows:
        by_gene[row["gene"]][row["group"]] = row
    selected = genes or [r["gene"] for r in sorted(clinical_rows, key=lambda r: (-r["n"], r["gene"]))][:10]
    selected = [g for g in selected if g in by_gene][:10]
    top = 58
    left = 120
    right = 90
    row_h = 28
    gap = 12
    height = top + len(selected) * (row_h + gap) + 60
    max_val = 1.0
    for gene in selected:
        for group in ("mutated", "not_mutated"):
            row = by_gene[gene].get(group, {})
            if metric == "death_rate":
                n = row.get("n") or 0
                val = (row.get("dead") or 0) / n * 100 if n else 0
            elif metric == "median_age":
                val = row.get("median_age_at_diagnosis_years") or 0
            elif metric == "stage_advanced_rate":
                n = row.get("n") or 0
                val = (row.get("stage_iii_or_iv") or 0) / n * 100 if n else 0
            else:
                val = 0
            max_val = max(max_val, float(val))
    scale_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="0" y="24" class="chart-title">{esc(title)}</text>',
        f'<rect x="{left}" y="36" width="16" height="10" fill="{COLORS["blue"]}"></rect>',
        f'<text x="{left + 22}" y="45" class="legend">Mutated</text>',
        f'<rect x="{left + 110}" y="36" width="16" height="10" fill="{COLORS["orange"]}"></rect>',
        f'<text x="{left + 132}" y="45" class="legend">Not mutated</text>',
    ]
    for i, gene in enumerate(selected):
        y = top + i * (row_h + gap)
        mut = by_gene[gene].get("mutated", {})
        wt = by_gene[gene].get("not_mutated", {})
        if metric == "death_rate":
            mut_val = (mut.get("dead") or 0) / (mut.get("n") or 1) * 100
            wt_val = (wt.get("dead") or 0) / (wt.get("n") or 1) * 100
            suffix = "% dead"
        elif metric == "median_age":
            mut_val = mut.get("median_age_at_diagnosis_years") or 0
            wt_val = wt.get("median_age_at_diagnosis_years") or 0
            suffix = " yrs"
        else:
            mut_val = (mut.get("stage_iii_or_iv") or 0) / (mut.get("n") or 1) * 100
            wt_val = (wt.get("stage_iii_or_iv") or 0) / (wt.get("n") or 1) * 100
            suffix = "% stage III/IV"
        mut_w = scale_w * float(mut_val) / max_val
        wt_w = scale_w * float(wt_val) / max_val
        parts.append(f'<text x="0" y="{y + 20}" class="axis-label">{esc(gene)}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{mut_w:.1f}" height="12" rx="3" fill="{COLORS["blue"]}"></rect>')
        parts.append(f'<rect x="{left}" y="{y + 16}" width="{wt_w:.1f}" height="12" rx="3" fill="{COLORS["orange"]}"></rect>')
        parts.append(
            f'<text x="{left + max(mut_w, wt_w) + 8:.1f}" y="{y + 20}" class="value-label">'
            f'{fmt_num(mut_val, 1)}{suffix} vs {fmt_num(wt_val, 1)}{suffix}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def survival_pvalue_chart(
    rows: list[dict[str, Any]],
    label_field: str,
    title: str,
    *,
    width: int = 840,
    max_items: int = 15,
) -> str:
    scored = []
    for row in rows:
        p = row.get("logrank_p_value")
        if p is None or p == "":
            continue
        p = float(p)
        scored.append((row[label_field], -math.log10(max(p, 1e-300))))
    scored.sort(key=lambda kv: -kv[1])
    counts = Counter({label: score for label, score in scored[:max_items]})
    return bar_chart(counts, title, width=width, color=COLORS["purple"], max_items=max_items)


def cohort_overview_chart(
    patient_count: int,
    slide_count: int,
    mutation_cases: int,
    expression_cases: int,
    width: int = 840,
) -> str:
    items = {
        "Patients/cases": patient_count,
        "Diagnostic slides": slide_count,
        "With mutation files": mutation_cases,
        "With RNA expression files": expression_cases,
    }
    return bar_chart(items, "Cohort size and data availability", width=width, color=COLORS["green"])


def export_standalone_plots(
    plots_dir: Path,
    *,
    patients: dict[str, dict[str, str]],
    mutation_freq: list[dict[str, Any]],
    clinical_rows: list[dict[str, Any]],
    mutation_survival: list[dict[str, Any]],
    mutation_plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
    rna_survival: list[dict[str, Any]],
    rna_plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
    protein_survival: list[dict[str, Any]],
    protein_plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
) -> list[str]:
    plots_dir.mkdir(parents=True, exist_ok=True)
    patient_rows = list(patients.values())
    project_counts = count_values(patient_rows, "project_id")
    sex_counts = count_values(patient_rows, "sex")
    race_counts = count_values(patient_rows, "race")
    ethnicity_counts = count_values(patient_rows, "ethnicity")
    smoking_counts = count_values(patient_rows, "tobacco_smoking_status")
    vital_counts = count_values(patient_rows, "vital_status")
    stage_counts = count_values(patient_rows, "ajcc_pathologic_stage")
    ages = [to_float(row.get("age_at_diagnosis_years")) for row in patient_rows]
    ages = [v for v in ages if v is not None]
    slide_count = sum(int(float(row.get("slide_count") or 0)) for row in patient_rows)
    mutation_cases = sum(1 for row in patient_rows if int(float(row.get("mutation_file_count") or 0)) > 0)
    expression_cases = sum(1 for row in patient_rows if int(float(row.get("expression_file_count") or 0)) > 0)

    top_genes = [r["gene"] for r in mutation_freq[:10]]
    plot_specs: list[tuple[str, str]] = [
        ("01_cohort_size_and_availability.svg", cohort_overview_chart(len(patient_rows), slide_count, mutation_cases, expression_cases)),
        ("02_luad_vs_lusc_patient_counts.svg", bar_chart(project_counts, "LUAD vs LUSC patient counts", color=COLORS["purple"])),
        ("03_age_distribution.svg", histogram(ages, "Age distribution at diagnosis")),
        ("04_sex_distribution.svg", bar_chart(sex_counts, "Sex distribution", color=COLORS["blue"])),
        ("05_race_distribution.svg", bar_chart(race_counts, "Race distribution", color=COLORS["green"])),
        ("06_ethnicity_distribution.svg", bar_chart(ethnicity_counts, "Ethnicity distribution", color=COLORS["orange"])),
        ("07_smoking_history.svg", bar_chart(smoking_counts, "Smoking history", color=COLORS["gray"])),
        ("08_ajcc_pathologic_stage.svg", bar_chart(stage_counts, "AJCC pathologic stage", color=COLORS["purple"])),
        ("09_vital_status.svg", bar_chart(vital_counts, "Vital status", color=COLORS["red"])),
        ("10_driver_mutation_frequency_luad_lusc.svg", grouped_mutation_chart(mutation_freq, "Driver mutation frequency by LUAD/LUSC")),
        (
            "11_clinical_death_rate_by_mutation_status.svg",
            clinical_comparison_chart(clinical_rows, "Death rate by mutation status (top genes)", "death_rate", genes=top_genes),
        ),
        (
            "12_clinical_median_age_by_mutation_status.svg",
            clinical_comparison_chart(clinical_rows, "Median age by mutation status (top genes)", "median_age", genes=top_genes),
        ),
        (
            "13_clinical_advanced_stage_by_mutation_status.svg",
            clinical_comparison_chart(clinical_rows, "Stage III/IV rate by mutation status (top genes)", "stage_advanced_rate", genes=top_genes),
        ),
        ("14_mutation_survival_pvalues.svg", survival_pvalue_chart(mutation_survival, "gene", "Mutation survival association strength (-log10 p)")),
        ("15_rna_expression_survival_pvalues.svg", survival_pvalue_chart(rna_survival, "gene", "RNA expression survival association strength (-log10 p)")),
        (
            "16_protein_expression_survival_pvalues.svg",
            survival_pvalue_chart(protein_survival, "protein_target", "RPPA protein survival association strength (-log10 p)"),
        ),
    ]

    sig_mutation = significant_survival_rows(mutation_survival)
    sig_rna = significant_survival_rows(rna_survival)
    sig_protein = significant_survival_rows(protein_survival)

    significant_km_dir = plots_dir / "significant_km"
    significant_km_dir.mkdir(parents=True, exist_ok=True)
    for old in plots_dir.glob("*survival_km*.svg"):
        old.unlink(missing_ok=True)
    for old in significant_km_dir.glob("*.svg"):
        old.unlink(missing_ok=True)

    for row in sig_mutation:
        g = row["gene"]
        if g not in mutation_plot_groups:
            continue
        filename = f"mutation_km_{g}.svg"
        plot_specs.append(
            (
                f"significant_km/{filename}",
                km_curve(
                    *mutation_plot_groups[g],
                    title=f"Survival by {g} mutation status",
                    group_a_label="Mutated",
                    group_b_label="Not mutated",
                    p_value=to_float(row.get("logrank_p_value")),
                ),
            )
        )
    for row in sig_rna:
        g = row["gene"]
        if g not in rna_plot_groups:
            continue
        filename = f"rna_km_{g}.svg"
        plot_specs.append(
            (
                f"significant_km/{filename}",
                km_curve(
                    *rna_plot_groups[g],
                    title=f"Survival by {g} RNA expression (median split)",
                    group_a_label="High expression",
                    group_b_label="Low expression",
                    p_value=to_float(row.get("logrank_p_value")),
                ),
            )
        )
    for row in sig_protein:
        target = row["protein_target"]
        if target not in protein_plot_groups:
            continue
        safe = target.replace("/", "_")
        filename = f"protein_km_{safe}.svg"
        plot_specs.append(
            (
                f"significant_km/{filename}",
                km_curve(
                    *protein_plot_groups[target],
                    title=f"Survival by {target} RPPA expression (median split)",
                    group_a_label="High protein",
                    group_b_label="Low protein",
                    p_value=to_float(row.get("logrank_p_value")),
                ),
            )
        )

    written: list[str] = []
    for filename, svg in plot_specs:
        path = plots_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        write_svg(path, svg)
        written.append(filename)

    manifest = {
        "significance_alpha": SIGNIFICANCE_ALPHA,
        "significant_mutation_curves": [r["gene"] for r in sig_mutation],
        "significant_rna_curves": [r["gene"] for r in sig_rna],
        "significant_protein_curves": [r["protein_target"] for r in sig_protein],
        "plot_files": [name for name in written if name.startswith("significant_km/")],
    }
    write_json(plots_dir / "significant_km_manifest.json", manifest)

    gallery_items = "\n".join(
        f'    <section class="plot-card"><h3>{esc(name)}</h3><img src="plots/{esc(name)}" alt="{esc(name)}"></section>'
        for name in written
    )
    gallery = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TCGA Lung Plot Gallery</title>
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
  <h1>TCGA Lung Plot Gallery</h1>
  <p class="subtitle">Standalone SVG plots for cohort demographics, driver mutations, clinical comparisons, and exploratory survival associations. Also see <a href="index.html">index.html</a> for the full report.</p>
  <div class="grid">
{gallery_items}
  </div>
</body>
</html>
"""
    (plots_dir.parent / "gallery.html").write_text(gallery)
    return written


def table_html(rows: list[dict[str, Any]], fields: list[str], *, limit: int = 12) -> str:
    shown = rows[:limit]
    if not shown:
        return "<p>No rows available.</p>"
    parts = ["<table>", "<thead><tr>"]
    for field in fields:
        parts.append(f"<th>{esc(field)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in shown:
        parts.append("<tr>")
        for field in fields:
            val = row.get(field)
            if isinstance(val, float):
                val = fmt_num(val, 4 if "p_value" in field else 2)
            parts.append(f"<td>{esc(val)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def render_report(
    out_dir: Path,
    patients: dict[str, dict[str, str]],
    mutation_freq: list[dict[str, Any]],
    clinical_rows: list[dict[str, Any]],
    mutation_survival: list[dict[str, Any]],
    mutation_plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
    rna_survival: list[dict[str, Any]],
    rna_plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
    protein_survival: list[dict[str, Any]],
    protein_plot_groups: dict[str, tuple[list[dict[str, float]], list[dict[str, float]]]],
) -> str:
    patient_rows = list(patients.values())
    project_counts = count_values(patient_rows, "project_id")
    sex_counts = count_values(patient_rows, "sex")
    race_counts = count_values(patient_rows, "race")
    ethnicity_counts = count_values(patient_rows, "ethnicity")
    smoking_counts = count_values(patient_rows, "tobacco_smoking_status")
    vital_counts = count_values(patient_rows, "vital_status")
    stage_counts = count_values(patient_rows, "ajcc_pathologic_stage")
    ages = [to_float(row.get("age_at_diagnosis_years")) for row in patient_rows]
    ages = [v for v in ages if v is not None]
    slide_count = sum(int(float(row.get("slide_count") or 0)) for row in patient_rows)
    mutation_cases = sum(1 for row in patient_rows if int(float(row.get("mutation_file_count") or 0)) > 0)
    expression_cases = sum(1 for row in patient_rows if int(float(row.get("expression_file_count") or 0)) > 0)

    mutation_km = km_curves_html(
        mutation_survival,
        mutation_plot_groups,
        key_field="gene",
        group_a_label="Mutated",
        group_b_label="Not mutated",
        title_prefix="Mutation",
    )
    rna_km = km_curves_html(
        rna_survival,
        rna_plot_groups,
        key_field="gene",
        group_a_label="High expression",
        group_b_label="Low expression",
        title_prefix="RNA expression",
    )
    protein_km = km_curves_html(
        protein_survival,
        protein_plot_groups,
        key_field="protein_target",
        group_a_label="High protein",
        group_b_label="Low protein",
        title_prefix="RPPA protein",
    )

    cards = [
        ("Patients/cases", len(patient_rows)),
        ("Diagnostic slides", slide_count),
        ("Patients with mutation files", mutation_cases),
        ("Patients with RNA expression files", expression_cases),
        ("Median age at diagnosis", fmt_num(median(ages), 1)),
        ("Deaths recorded", vital_counts.get("Dead", 0)),
    ]

    card_html = "\n".join(
        f'<div class="card"><div class="card-value">{esc(value)}</div><div class="card-label">{esc(label)}</div></div>'
        for label, value in cards
    )

    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TCGA Lung Important Gene Visual Summary</title>
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
  <h1>TCGA Lung Important Gene Visual Summary</h1>
  <p class="subtitle">Focused visualization of the TCGA-LUAD and TCGA-LUSC slide-cohort patients, important driver-gene mutations, clinical demographics, RNA expression, RPPA protein expression, and exploratory survival associations.</p>

  <div class="cards">{card_html}</div>

  <div class="panel">
    <h2>1. Cohort overview</h2>
    <div class="grid">
      <div>{bar_chart(project_counts, "Patients by TCGA project", color=COLORS["purple"])}</div>
      <div>{histogram(ages, "Age distribution")}</div>
      <div>{bar_chart(sex_counts, "Sex", color=COLORS["blue"])}</div>
      <div>{bar_chart(vital_counts, "Vital status", color=COLORS["red"])}</div>
    </div>
  </div>

  <div class="panel">
    <h2>2. Demographics and clinical variables</h2>
    <div class="grid">
      <div>{bar_chart(race_counts, "Race", color=COLORS["green"])}</div>
      <div>{bar_chart(ethnicity_counts, "Ethnicity", color=COLORS["orange"])}</div>
      <div>{bar_chart(smoking_counts, "Smoking history", color=COLORS["gray"])}</div>
      <div>{bar_chart(stage_counts, "AJCC pathologic stage", color=COLORS["purple"])}</div>
    </div>
  </div>

  <div class="panel">
    <h2>3. Driver mutation statistics</h2>
    <p class="note">Mutation frequencies are based on patients with public masked somatic mutation MAF files. These are SNV/indel calls; copy-number events and fusions require separate assays.</p>
    {grouped_mutation_chart(mutation_freq, "Important-gene mutation frequency by disease")}
    <h3>Top mutation frequencies</h3>
    {table_html(mutation_freq, ["gene", "mutated_cases", "analyzable_cases", "overall_pct", "luad_mutated", "luad_total", "luad_pct", "lusc_mutated", "lusc_total", "lusc_pct"], limit=15)}
  </div>

  <div class="panel">
    <h2>4. Clinical differences by mutation status</h2>
    <p class="note">This table summarizes mutated vs not-mutated groups for each gene. Full table: <code>clinical_by_driver_mutation.csv</code>.</p>
    {table_html(clinical_rows, ["gene", "group", "n", "median_age_at_diagnosis_years", "female", "male", "alive", "dead", "stage_i_or_ii", "stage_iii_or_iv", "progression_or_recurrence_reported_yes"], limit=18)}
  </div>

  <div class="panel">
    <h2>5. Exploratory survival associations</h2>
    <p class="note">Kaplan-Meier/log-rank summaries are exploratory and unadjusted. Only curves with log-rank p &lt; {SIGNIFICANCE_ALPHA} are plotted below. Y-axis = survival probability (fraction alive). X-axis = follow-up time in days from TCGA clinical fields.</p>
    <h3>Significant mutation status vs survival</h3>
    {table_html([r for r in mutation_survival if is_significant(r)], ["gene", "mutated_n", "not_mutated_n", "mutated_events", "not_mutated_events", "mutated_km_median_survival_days", "not_mutated_km_median_survival_days", "logrank_p_value"], limit=12)}
    {mutation_km}
    <h3>Significant RNA expression vs survival</h3>
    {table_html([r for r in rna_survival if is_significant(r)], ["gene", "median_split_cutoff", "high_n", "low_n", "high_events", "low_events", "high_km_median_survival_days", "low_km_median_survival_days", "logrank_p_value"], limit=12)}
    {rna_km}
    <h3>Significant protein/RPPA expression vs survival</h3>
    {table_html([r for r in protein_survival if is_significant(r)], ["protein_target", "gene", "median_split_cutoff", "high_n", "low_n", "high_events", "low_events", "high_km_median_survival_days", "low_km_median_survival_days", "logrank_p_value"], limit=12)}
    {protein_km}
  </div>

  <div class="panel">
    <h2>6. Resistance/progression caveat</h2>
    <p class="note">The current public clinical table has survival, disease response, progression/recurrence, and treatment outcome fields, but direct drug-resistance labels are sparse/not uniformly available. The report therefore uses survival and progression/recurrence as exploratory clinical endpoints.</p>
  </div>

  <div class="panel">
    <h2>Generated files</h2>
    <p class="note">Open <a href="gallery.html"><code>gallery.html</code></a> to browse every standalone SVG plot, or inspect files under <code>plots/</code>.</p>
    <ul>
      <li><code>index.html</code> - this visual report</li>
      <li><code>gallery.html</code> - standalone plot gallery for Cursor/browser preview</li>
      <li><code>plots/significant_km/</code> - Kaplan-Meier curves with log-rank p &lt; {SIGNIFICANCE_ALPHA}</li>
      <li><code>plots/significant_km_manifest.json</code> - list of significant KM curves</li>
      <li><code>cohort_visual_summary.json</code> - report-level summary counts</li>
      <li><code>driver_mutation_frequency.csv</code> - mutation frequencies by LUAD/LUSC</li>
      <li><code>clinical_by_driver_mutation.csv</code> - clinical summaries by mutation status</li>
      <li><code>mutation_survival_associations.csv</code> - log-rank mutation survival comparisons</li>
      <li><code>rna_expression_survival_associations.csv</code> - median-split RNA survival comparisons</li>
      <li><code>protein_expression_survival_associations.csv</code> - median-split RPPA survival comparisons</li>
    </ul>
  </div>
</body>
</html>
"""
    (out_dir / "index.html").write_text(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_data_dir = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=default_data_dir)
    parser.add_argument(
        "--important-dir",
        type=Path,
        default=default_data_dir / "important_lung_genes",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_data_dir / "important_lung_genes" / "visual_report",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    patient_rows = read_csv(args.data_dir / "patient_metadata.tcga_lung.csv")
    patients = {row["case_id"]: row for row in patient_rows}
    mutations = read_csv(args.important_dir / "important_mutations.tcga_lung.csv")
    rna_rows = read_csv(args.important_dir / "important_gene_expression.tcga_lung.csv")
    protein_rows = read_csv(args.important_dir / "important_protein_expression.tcga_lung.csv")

    mutated_by_gene, mutation_freq = build_mutation_status(mutations, patients)
    clinical_rows = clinical_by_mutation(patients, mutated_by_gene)
    mutation_survival, mutation_plot_groups = mutation_survival_associations(patients, mutated_by_gene)

    rna_values = expression_matrix(rna_rows, "tpm_unstranded", "gene")
    rna_survival, rna_plot_groups = median_split_survival_associations(
        patients,
        rna_values,
        "gene",
        min_group=30,
    )

    protein_value_by_case_target: dict[tuple[str, str], list[float]] = defaultdict(list)
    target_to_gene: dict[str, str] = {}
    for row in protein_rows:
        target = row.get("peptide_target")
        value = to_float(row.get("protein_expression"))
        case_id = row.get("case_id")
        if not target or value is None or not case_id:
            continue
        protein_value_by_case_target[(case_id, target)].append(value)
        target_to_gene[target] = row.get("gene", "")
    protein_values = {
        key: statistics.mean(vals) for key, vals in protein_value_by_case_target.items() if vals
    }
    protein_survival, protein_plot_groups = median_split_survival_associations(
        patients,
        protein_values,
        "protein_target",
        min_group=30,
    )
    for row in protein_survival:
        row["gene"] = target_to_gene.get(row["protein_target"], "")

    mutation_freq_fields = [
        "gene",
        "mutated_cases",
        "analyzable_cases",
        "overall_pct",
        "luad_mutated",
        "luad_total",
        "luad_pct",
        "lusc_mutated",
        "lusc_total",
        "lusc_pct",
    ]
    clinical_fields = [
        "gene",
        "group",
        "n",
        "median_age_at_diagnosis_years",
        "female",
        "male",
        "white",
        "black_or_african_american",
        "asian",
        "alive",
        "dead",
        "median_survival_time_days_observed",
        "stage_i_or_ii",
        "stage_iii_or_iv",
        "progression_or_recurrence_reported_yes",
        "disease_response_values",
    ]
    mutation_survival_fields = [
        "gene",
        "mutated_n",
        "not_mutated_n",
        "mutated_events",
        "not_mutated_events",
        "mutated_km_median_survival_days",
        "not_mutated_km_median_survival_days",
        "logrank_chi_square",
        "logrank_p_value",
    ]
    expression_survival_fields = [
        "gene",
        "median_split_cutoff",
        "high_n",
        "low_n",
        "high_events",
        "low_events",
        "high_km_median_survival_days",
        "low_km_median_survival_days",
        "logrank_chi_square",
        "logrank_p_value",
    ]
    protein_survival_fields = [
        "protein_target",
        "gene",
        "median_split_cutoff",
        "high_n",
        "low_n",
        "high_events",
        "low_events",
        "high_km_median_survival_days",
        "low_km_median_survival_days",
        "logrank_chi_square",
        "logrank_p_value",
    ]

    write_csv(args.out_dir / "driver_mutation_frequency.csv", mutation_freq, mutation_freq_fields)
    write_csv(args.out_dir / "clinical_by_driver_mutation.csv", clinical_rows, clinical_fields)
    write_csv(args.out_dir / "mutation_survival_associations.csv", mutation_survival, mutation_survival_fields)
    write_csv(args.out_dir / "rna_expression_survival_associations.csv", rna_survival, expression_survival_fields)
    write_csv(args.out_dir / "protein_expression_survival_associations.csv", protein_survival, protein_survival_fields)

    cohort_summary = {
        "patient_count": len(patient_rows),
        "slide_count": sum(int(float(row.get("slide_count") or 0)) for row in patient_rows),
        "project_counts": dict(count_values(patient_rows, "project_id")),
        "sex_counts": dict(count_values(patient_rows, "sex")),
        "race_counts": dict(count_values(patient_rows, "race")),
        "ethnicity_counts": dict(count_values(patient_rows, "ethnicity")),
        "vital_status_counts": dict(count_values(patient_rows, "vital_status")),
        "mutation_analyzable_patients": sum(1 for row in patient_rows if int(float(row.get("mutation_file_count") or 0)) > 0),
        "expression_analyzable_patients": sum(1 for row in patient_rows if int(float(row.get("expression_file_count") or 0)) > 0),
        "important_mutation_rows": len(mutations),
        "important_rna_expression_rows": len(rna_rows),
        "important_protein_expression_rows": len(protein_rows),
        "mutation_survival_tests": len(mutation_survival),
        "rna_survival_tests": len(rna_survival),
        "protein_survival_tests": len(protein_survival),
        "method_notes": [
            "Report uses public TCGA/GDC data already extracted in this repository.",
            "Survival tests are unadjusted two-group log-rank comparisons.",
            "RNA and protein survival tests use median splits and should be treated as exploratory.",
            "Resistance is approximated with available progression/recurrence, disease response, and survival fields because direct resistance labels are sparse.",
        ],
    }
    write_json(args.out_dir / "cohort_visual_summary.json", cohort_summary)

    render_report(
        args.out_dir,
        patients,
        mutation_freq,
        clinical_rows,
        mutation_survival,
        mutation_plot_groups,
        rna_survival,
        rna_plot_groups,
        protein_survival,
        protein_plot_groups,
    )

    plot_files = export_standalone_plots(
        args.out_dir / "plots",
        patients=patients,
        mutation_freq=mutation_freq,
        clinical_rows=clinical_rows,
        mutation_survival=mutation_survival,
        mutation_plot_groups=mutation_plot_groups,
        rna_survival=rna_survival,
        rna_plot_groups=rna_plot_groups,
        protein_survival=protein_survival,
        protein_plot_groups=protein_plot_groups,
    )

    print(f"Wrote visual report to {args.out_dir / 'index.html'}")
    print(f"Wrote plot gallery to {args.out_dir / 'gallery.html'}")
    print(f"Wrote {len(plot_files)} standalone SVG plots to {args.out_dir / 'plots'}")
    print(json.dumps(cohort_summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
