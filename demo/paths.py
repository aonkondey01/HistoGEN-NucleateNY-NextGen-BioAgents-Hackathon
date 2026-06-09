"""Canonical paths for the 20-patient HistoGEN demo cohort."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_ROOT = Path(__file__).resolve().parent

PATIENTS_JSON = DEMO_ROOT / "representative_20_patients.json"
PATIENTS_CSV = DEMO_ROOT / "representative_20_patients.csv"
BUNDLE_ROOT = DEMO_ROOT / "data_package" / "per_patient"
VISUAL_REPORT = DEMO_ROOT / "visual_report"
GENOMIC_DATA = DEMO_ROOT / "genomic_data"

WSI_DIR = DEMO_ROOT / "WSI"
PHOENIX_DIR = DEMO_ROOT / "phoenix"
PHOENIX_ATLAS = PHOENIX_DIR / "tcga-atlas-nest-multi-cell-20x-discrete.h5ad"
GIGATIME_DIR = DEMO_ROOT / "gigatime"
GIGATIME_OUT = GIGATIME_DIR / "outputs"
HAIKU_DIR = DEMO_ROOT / "haiku"

# Fallback when atlas was fetched to the general phoenix helper location.
LEGACY_PHOENIX_ATLAS = REPO_ROOT / "data" / "phoenix" / "atlas" / "tcga-atlas-nest-multi-cell-20x-discrete.h5ad"
GIGATIME_WEIGHTS = REPO_ROOT / "data" / "gigatime"
TCGA_LUNG = REPO_ROOT / "data" / "tcga_lung"
SLIDES_META = TCGA_LUNG / "slides_metadata.tcga_lung.json"
MANIFEST = TCGA_LUNG / "gdc_manifest.tcga_lung.txt"

DEFAULT_CASE_ID = "TCGA-55-7815"


def atlas_path() -> Path:
    if PHOENIX_ATLAS.is_file():
        return PHOENIX_ATLAS
    if LEGACY_PHOENIX_ATLAS.is_file():
        return LEGACY_PHOENIX_ATLAS
    return PHOENIX_ATLAS


def bundle_dir(case_id: str) -> Path:
    return BUNDLE_ROOT / case_id


def slide_preview(case_id: str, kind: str = "thumbnail") -> Path | None:
    previews = bundle_dir(case_id) / "slide_previews"
    if not previews.is_dir():
        return None
    matches = sorted(previews.glob(f"{case_id}*.{kind}.png"))
    return matches[0] if matches else None


def find_wsi(case_id: str) -> Path | None:
    hits = sorted(WSI_DIR.rglob(f"*{case_id}*.svs"))
    if hits:
        return hits[0]
    legacy = TCGA_LUNG / "WSI"
    if legacy.is_dir():
        hits = sorted(legacy.rglob(f"*{case_id}*.svs"))
        if hits:
            return hits[0]
    return None
