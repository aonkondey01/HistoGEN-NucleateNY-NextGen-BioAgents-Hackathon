"""Build PHOENIX per-patient bundles from the downloaded atlas AnnData."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PHOENIX_DIR = REPO_ROOT / "data" / "phoenix"
EXTRACT = PHOENIX_DIR / "extract_slide_readouts.py"
REGISTER = PHOENIX_DIR / "register_phoenix_to_he.py"
BUNDLE_ROOT = REPO_ROOT / "demo" / "data_package" / "per_patient"

sys.path.insert(0, str(REPO_ROOT / "demo"))
from paths import atlas_path, find_wsi  # noqa: E402


def _registered_cells(case_id: str) -> Path:
    return BUNDLE_ROOT / case_id / "phoenix_registration" / "phoenix_cells_registered.csv"


def _summary_path(case_id: str) -> Path:
    return BUNDLE_ROOT / case_id / "phoenix_summary.json"


def has_registered_bundle(case_id: str) -> bool:
    return _registered_cells(case_id).is_file()


def has_extracted_bundle(case_id: str) -> bool:
    return _summary_path(case_id).is_file() and (BUNDLE_ROOT / case_id / "phoenix_cells.csv").is_file()


def ensure_phoenix_bundle(case_id: str, *, register: bool = True) -> bool:
    """Extract PHOENIX readouts from AnnData and run contour+flow registration when possible."""
    if register and has_registered_bundle(case_id):
        return True
    if not register and has_extracted_bundle(case_id):
        return True

    atlas = atlas_path()
    if not atlas.is_file():
        return has_extracted_bundle(case_id)

    bundle_dir = BUNDLE_ROOT / case_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    if not has_extracted_bundle(case_id):
        previews = bundle_dir / "slide_previews"
        cmd = [
            sys.executable,
            str(EXTRACT),
            "--case",
            case_id,
            "--atlas",
            str(atlas),
            "--out-dir",
            str(bundle_dir),
        ]
        if previews.is_dir() and any(previews.glob("*.png")):
            cmd.extend(["--previews-dir", str(previews)])
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    if register and not has_registered_bundle(case_id):
        svs = find_wsi(case_id)
        if svs is None:
            return has_extracted_bundle(case_id)
        subprocess.run(
            [
                sys.executable,
                str(REGISTER),
                "--case",
                case_id,
                "--svs",
                str(svs),
            ],
            cwd=REPO_ROOT,
            check=True,
        )

    return has_extracted_bundle(case_id)


def clear_phoenix_caches() -> None:
    from phoenix_data import load_gene_summary, load_summary, thumbnail_size

    load_summary.cache_clear()
    load_gene_summary.cache_clear()
    thumbnail_size.cache_clear()
