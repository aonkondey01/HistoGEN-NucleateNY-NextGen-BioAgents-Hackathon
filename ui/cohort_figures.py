"""Cohort visual-report figures for the HistoGen Advisor demo knowledge base."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
VISUAL_REPORT = REPO_ROOT / "demo/visual_report"
SELECTED_DIR = VISUAL_REPORT / "selected figures"
MANIFEST_PATH = SELECTED_DIR / "manifest.json"
SUMMARY_PATH = VISUAL_REPORT / "cohort_visual_summary.json"
DATA_URL_PREFIX = "/demo/visual_report/selected%20figures"

FIGURE_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "slide05_age_at_diagnosis_distribution": {
        "keywords": ["age", "diagnosis", "demographic", "years old", "elderly", "young"],
        "summary": (
            "Age at diagnosis for the 20 representative TCGA lung patients. "
            "The cohort spans adult ages with LUAD/LUSC and smoker/non-smoker strata represented."
        ),
        "demoPrompts": ["show cohort age distribution", "age at diagnosis"],
    },
    "slide07_vital_status": {
        "keywords": ["vital", "alive", "dead", "survival", "overall survival", "os status", "deceased"],
        "summary": "Vital status across the representative TCGA lung cohort used for this demo.",
        "demoPrompts": ["show vital status", "cohort survival overview"],
    },
    "slide08_sex_distribution": {
        "keywords": ["sex", "gender", "male", "female", "demographic"],
        "summary": "Sex distribution for the 20-patient representative TCGA lung cohort.",
        "demoPrompts": ["show sex distribution", "cohort gender breakdown"],
    },
    "slide09_ajcc_pathologic_stage": {
        "keywords": ["stage", "ajcc", "pathologic", "staging", "tnm", "advanced"],
        "summary": (
            "AJCC pathologic stage distribution for the representative patients — useful when "
            "linking spatial TME phenotypes to stage at diagnosis."
        ),
        "demoPrompts": ["show pathologic stage", "AJCC stage distribution"],
    },
    "slide14_top_driver_gene_mutation_frequency": {
        "keywords": [
            "driver",
            "mutation",
            "mutations",
            "egfr",
            "kras",
            "tp53",
            "gene frequency",
            "oncogene",
        ],
        "summary": (
            "Top driver-gene mutation frequency across the 20 patients (TCGA masked MAF). "
            "Pair with the scatter plot colour-by driver mutation view in the main dashboard."
        ),
        "demoPrompts": ["show driver mutation frequency", "top mutated driver genes"],
    },
    "slide17_variant_classification_cohort_wide": {
        "keywords": [
            "variant",
            "classification",
            "missense",
            "truncating",
            "silent",
            "snv",
            "indel",
            "mutation class",
        ],
        "summary": (
            "Cohort-wide somatic variant classification breakdown from TCGA masked MAF."
        ),
        "demoPrompts": ["show variant classification", "mutation types in the cohort"],
    },
    "slide22_treatment_types_patient_mentions": {
        "keywords": [
            "treatment",
            "therapy",
            "chemo",
            "chemotherapy",
            "radiation",
            "immunotherapy",
            "platinum",
            "agents",
            "resistance",
        ],
        "summary": (
            "Treatment types documented per patient (TCGA clinical fields). "
            "Chemotherapy, radiation, and pharmaceutical therapy dominate; "
            "direct therapeutic-agent strings are sparse in public metadata."
        ),
        "demoPrompts": ["show treatment types", "what therapies did the cohort receive"],
    },
}

LIST_FIGURES_PATTERNS = [
    r"what (?:cohort )?(?:figures|plots|images) do you know",
    r"(?:list|show) (?:all )?(?:cohort )?(?:figures|plots)",
    r"cohort visual report",
    r"representative patient summary",
]


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Missing cohort figure manifest: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_cohort_summary() -> dict[str, Any]:
    if not SUMMARY_PATH.is_file():
        return {}
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def _figure_url(filename: str) -> str:
    return f"{DATA_URL_PREFIX}/{quote(filename)}"


def enrich_figure(entry: dict[str, Any]) -> dict[str, Any]:
    stem = entry["stem"]
    knowledge = FIGURE_KNOWLEDGE.get(stem, {})
    png = next((name for name in entry.get("files", []) if name.endswith(".png")), None)
    svg = next((name for name in entry.get("files", []) if name.endswith(".svg")), None)
    return {
        "title": entry.get("title"),
        "stem": stem,
        "summary": knowledge.get("summary", entry.get("title", "")),
        "keywords": knowledge.get("keywords", []),
        "demoPrompts": knowledge.get("demoPrompts", []),
        "pngUrl": _figure_url(png) if png else None,
        "svgUrl": _figure_url(svg) if svg else None,
        "source": "Representative_20_Patients_Summary.pptx",
    }


def list_figures() -> dict[str, Any]:
    manifest = load_manifest()
    figures = [enrich_figure(entry) for entry in manifest.get("figures", [])]
    summary = load_cohort_summary()
    return {
        "description": "Selected cohort figures memorized for HistoGen Advisor demo",
        "sourceBranch": "cursor/representative-patient-selection-c77c",
        "sourcePowerpoint": manifest.get("source_powerpoint"),
        "patientCount": summary.get("patient_count", 20),
        "projectCounts": summary.get("project_counts"),
        "smokingGroupCounts": summary.get("smoking_group_counts"),
        "methodNotes": summary.get("method_notes", []),
        "figureCount": len(figures),
        "figures": figures,
    }


def _score_figure(query: str, figure: dict[str, Any]) -> int:
    text = query.lower()
    score = 0
    title = (figure.get("title") or "").lower()
    if title and title in text:
        score += 12
    for token in title.split():
        if len(token) > 3 and token in text:
            score += 2
    stem = figure.get("stem", "")
    for keyword in figure.get("keywords", []):
        if keyword in text:
            score += 4
    if stem.replace("_", " ") in text.replace("-", " "):
        score += 8
    return score


def match_figure(query: str) -> dict[str, Any] | None:
    payload = list_figures()
    figures = payload["figures"]
    if not figures:
        return None

    normalized = query.strip().lower()
    for pattern in LIST_FIGURES_PATTERNS:
        if re.search(pattern, normalized):
            return {
                "matchType": "catalog",
                "query": query,
                "figures": figures,
                "cohort": payload,
            }

    best = max(figures, key=lambda fig: _score_figure(normalized, fig))
    if _score_figure(normalized, best) <= 0:
        return None

    return {
        "matchType": "figure",
        "query": query,
        "figure": best,
        "cohort": {
            "patientCount": payload.get("patientCount"),
        },
    }


def has_cohort_figures() -> bool:
    return MANIFEST_PATH.is_file() and any(SELECTED_DIR.glob("*.png"))
