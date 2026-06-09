"""Local demo cache for GigaTIME marker structures from Biohub ESM Atlas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

UI_DIR = Path(__file__).resolve().parent
CACHE_DIR = UI_DIR / "demo_cache" / "gigatime_structures"
MANIFEST_PATH = CACHE_DIR / "manifest.json"

# GigaTIME virtual mIF channels 3–22 (excluding DAPI + background TRITC/Cy5).
GIGATIME_MARKERS: list[dict[str, Any]] = [
    {"channel": "PD-1", "gene": "PDCD1", "aliases": ["PD1", "PD-1"]},
    {"channel": "CD14", "gene": "CD14", "aliases": ["CD14"]},
    {"channel": "CD4", "gene": "CD4", "aliases": ["CD4"]},
    {"channel": "T-bet", "gene": "TBX21", "aliases": ["TBET", "T-BET"]},
    {"channel": "CD34", "gene": "CD34", "aliases": ["CD34"]},
    {"channel": "CD68", "gene": "CD68", "aliases": ["CD68"]},
    {"channel": "CD16", "gene": "FCGR3A", "aliases": ["CD16"]},
    {"channel": "CD11c", "gene": "ITGAX", "aliases": ["CD11C", "CD11c"]},
    {"channel": "CD138", "gene": "SDC1", "aliases": ["CD138"]},
    {"channel": "CD20", "gene": "MS4A1", "aliases": ["CD20"]},
    {"channel": "CD3", "gene": "CD3E", "aliases": ["CD3", "CD3D"]},
    {"channel": "CD8", "gene": "CD8A", "aliases": ["CD8", "CD8B"]},
    {"channel": "PD-L1", "gene": "CD274", "aliases": ["PDL1", "PD-L1"]},
    {"channel": "CK", "gene": "KRT8", "aliases": ["CK", "KRT8", "KRT18"]},
    {"channel": "Ki67", "gene": "PCNA", "aliases": ["KI67", "KI-67", "MKI67"], "structure_note": "PCNA used as proliferation marker structure proxy (MKI67 exceeds ESM Atlas length limit)"},
    {"channel": "Tryptase", "gene": "TPSAB1", "aliases": ["TRYPTASE", "TPSAB1"]},
    {"channel": "Actin-D", "gene": "ACTA2", "aliases": ["ACTIN", "ACTA2"]},
    {"channel": "Caspase3-D", "gene": "CASP3", "aliases": ["CASP3", "CASPASE3"]},
    {"channel": "PHH3-B", "gene": "HIST1H3A", "aliases": ["PHH3", "HIST1H3A"]},
    {"channel": "Transgelin", "gene": "TAGLN", "aliases": ["TAGLN", "TRANSGELIN"]},
]

_ALIAS_TO_GENE: dict[str, str] = {}
for marker in GIGATIME_MARKERS:
    gene = marker["gene"].upper()
    _ALIAS_TO_GENE[gene] = gene
    _ALIAS_TO_GENE[marker["channel"].upper().replace("-", "")] = gene
    for alias in marker.get("aliases") or []:
        _ALIAS_TO_GENE[alias.upper().replace("-", "")] = gene


def normalize_gene_query(gene: str) -> str:
    key = gene.strip().upper().replace("-", "")
    return _ALIAS_TO_GENE.get(key, gene.strip().upper())


def marker_for_gene(gene: str) -> dict[str, Any] | None:
    canonical = normalize_gene_query(gene)
    for marker in GIGATIME_MARKERS:
        if marker["gene"].upper() == canonical:
            return marker
    return None


def cache_path(gene: str) -> Path:
    return CACHE_DIR / f"{normalize_gene_query(gene)}.json"


def load_cached_structure(gene: str) -> dict[str, Any] | None:
    path = cache_path(gene)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_cached_structure(gene: str, payload: dict[str, Any]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(gene)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def write_manifest(entries: list[dict[str, Any]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": "Cached Biohub ESM Atlas structures for GigaTIME virtual mIF markers (demo).",
        "marker_count": len(GIGATIME_MARKERS),
        "entries": entries,
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def list_demo_genes() -> list[dict[str, Any]]:
    cached = {path.stem.upper() for path in CACHE_DIR.glob("*.json") if path.name != "manifest.json"}
    rows: list[dict[str, Any]] = []
    for marker in GIGATIME_MARKERS:
        gene = marker["gene"].upper()
        rows.append(
            {
                "channel": marker["channel"],
                "gene": gene,
                "aliases": marker.get("aliases") or [],
                "cached": gene in cached,
            }
        )
    return rows
