#!/usr/bin/env python3
"""Generate download manifests for the lung TCGA H&E (FFPE diagnostic) slides.

This queries the NCI Genomic Data Commons (GDC) REST API for every diagnostic
(FFPE, H&E-stained) whole-slide image in the two lung TCGA projects:

    * TCGA-LUAD  - Lung Adenocarcinoma
    * TCGA-LUSC  - Lung Squamous Cell Carcinoma

It writes, into ``--out-dir`` (default: this directory):

    * ``gdc_manifest.tcga_lung.txt``      - combined GDC manifest (gdc-client format)
    * ``gdc_manifest.TCGA-LUAD.txt``      - per-project manifest
    * ``gdc_manifest.TCGA-LUSC.txt``      - per-project manifest
    * ``slides_metadata.tcga_lung.json``  - rich per-slide metadata (case/patient ids,
                                            project, file size, md5, ...)
    * ``summary.json``                    - counts + total size for quick reference

All of these slides are *open access* (no dbGaP / controlled-access token needed).

Why "diagnostic slides"? TCGA contains both frozen-tissue (``-TS``/``-BS``) and
FFPE diagnostic (``-DX``) slides. The FFPE diagnostic slides are the
H&E-stained, computation-grade images used for pathology foundation models.
The GDC field ``experimental_strategy == "Diagnostic Slide"`` selects exactly
those.

Usage:
    python generate_manifest.py                 # write everything to ./
    python generate_manifest.py --out-dir /data # custom output directory
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GDC_FILES_ENDPOINT = "https://api.gdc.cancer.gov/files"

LUNG_PROJECTS = ["TCGA-LUAD", "TCGA-LUSC"]

# Fields pulled back for each slide. These are useful downstream for the
# pathology foundation-model dashboard (linking slides -> patients/cases).
METADATA_FIELDS = [
    "file_id",
    "file_name",
    "md5sum",
    "file_size",
    "state",
    "data_format",
    "data_type",
    "experimental_strategy",
    "cases.project.project_id",
    "cases.submitter_id",
    "cases.case_id",
    "cases.samples.sample_type",
    "cases.samples.submitter_id",
]


def _base_filters() -> dict[str, Any]:
    """GDC filter selecting lung diagnostic (FFPE H&E) slide images."""
    return {
        "op": "and",
        "content": [
            {
                "op": "in",
                "content": {
                    "field": "cases.project.project_id",
                    "value": LUNG_PROJECTS,
                },
            },
            {
                "op": "in",
                "content": {"field": "files.data_type", "value": ["Slide Image"]},
            },
            {
                "op": "in",
                "content": {
                    "field": "files.experimental_strategy",
                    "value": ["Diagnostic Slide"],
                },
            },
        ],
    }


def _post(payload: dict[str, Any], *, expect_json: bool, retries: int = 4) -> Any:
    """POST to the GDC files endpoint with simple exponential-backoff retries."""
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
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if expect_json else raw
        except (urllib.error.URLError, TimeoutError) as err:  # network hiccup
            last_err = err
            wait = 4 * (2**attempt)
            print(
                f"  [retry {attempt + 1}/{retries}] GDC request failed: {err}; "
                f"waiting {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError(f"GDC request failed after {retries} attempts: {last_err}")


def fetch_manifest(project_ids: list[str]) -> str:
    """Return a gdc-client manifest (TSV text) for the given lung project(s)."""
    filters = _base_filters()
    filters["content"][0]["content"]["value"] = project_ids
    payload = {
        "filters": filters,
        "return_type": "manifest",
        "size": 100000,
    }
    return _post(payload, expect_json=False)


def fetch_metadata() -> list[dict[str, Any]]:
    """Return rich per-slide metadata records for all lung diagnostic slides."""
    payload = {
        "filters": _base_filters(),
        "fields": ",".join(METADATA_FIELDS),
        "format": "JSON",
        "size": 100000,
    }
    result = _post(payload, expect_json=True)
    return result["data"]["hits"]


def _flatten(hit: dict[str, Any]) -> dict[str, Any]:
    """Flatten a GDC file hit into a single dashboard-friendly record."""
    cases = hit.get("cases", [{}])
    case = cases[0] if cases else {}
    samples = case.get("samples", [{}])
    sample = samples[0] if samples else {}
    return {
        "file_id": hit.get("file_id"),
        "file_name": hit.get("file_name"),
        "md5sum": hit.get("md5sum"),
        "file_size": hit.get("file_size"),
        "state": hit.get("state"),
        "data_format": hit.get("data_format"),
        "project_id": (case.get("project") or {}).get("project_id"),
        "case_submitter_id": case.get("submitter_id"),
        "case_id": case.get("case_id"),
        "sample_type": sample.get("sample_type"),
        "sample_submitter_id": sample.get("submitter_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory to write manifests + metadata (default: script directory)",
    )
    args = parser.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Querying GDC for lung TCGA diagnostic (FFPE H&E) slides ...")

    # Per-project manifests.
    per_project_counts: dict[str, int] = {}
    for project in LUNG_PROJECTS:
        manifest = fetch_manifest([project])
        path = out_dir / f"gdc_manifest.{project}.txt"
        path.write_text(manifest)
        # First line is the header, remaining non-empty lines are slides.
        n = sum(1 for ln in manifest.splitlines()[1:] if ln.strip())
        per_project_counts[project] = n
        print(f"  {project}: {n} slides -> {path.name}")

    # Combined manifest (what you feed to gdc-client to grab everything).
    combined = fetch_manifest(LUNG_PROJECTS)
    combined_path = out_dir / "gdc_manifest.tcga_lung.txt"
    combined_path.write_text(combined)
    n_combined = sum(1 for ln in combined.splitlines()[1:] if ln.strip())
    print(f"  COMBINED: {n_combined} slides -> {combined_path.name}")

    # Rich metadata.
    print("Fetching per-slide metadata ...")
    hits = fetch_metadata()
    records = [_flatten(h) for h in hits]
    records.sort(key=lambda r: (r["project_id"] or "", r["file_name"] or ""))
    meta_path = out_dir / "slides_metadata.tcga_lung.json"
    meta_path.write_text(json.dumps(records, indent=2))
    print(f"  {len(records)} metadata records -> {meta_path.name}")

    # Summary.
    total_bytes = sum(r["file_size"] or 0 for r in records)
    unique_patients = len({r["case_submitter_id"] for r in records if r["case_submitter_id"]})
    summary = {
        "projects": LUNG_PROJECTS,
        "data_type": "Slide Image",
        "experimental_strategy": "Diagnostic Slide (FFPE, H&E)",
        "access": "open",
        "slides_per_project": per_project_counts,
        "total_slides": n_combined,
        "unique_patients": unique_patients,
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / 1e9, 1),
        "total_tb": round(total_bytes / 1e12, 3),
        "generated_unix": int(time.time()),
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print("\nSummary")
    print("-------")
    print(f"  total slides     : {summary['total_slides']}")
    print(f"  unique patients  : {summary['unique_patients']}")
    print(f"  total size       : {summary['total_gb']} GB ({summary['total_tb']} TB)")
    print(f"  written to       : {out_dir}")
    print("\nNext: download with")
    print(f"  python download.py --manifest {combined_path.name} --out-dir ./WSI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
