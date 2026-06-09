#!/usr/bin/env python3
"""Run PHOENIX virtual spatial transcriptomics inference on an H&E slide.

Loads flow-matching weights from ``data/phoenix/`` (see ``fetch.py``) and writes
per-cell gene readouts + UI bundle artifacts under ``--out-dir``.

For production inference, install the upstream package and follow
https://github.com/peng-lab/phoenix — this script validates weights, tiles the
slide, and writes the HistoGEN bundle format. The forward pass stub is replaced
when ``phoenix`` + ``FlowPipeline`` are available.

Usage:
    python fetch.py
    python inference.py --svs /path/to/slide.svs --out-dir ./outputs/my_case
    python inference.py --svs slide.svs --out-dir ./outputs/my_case --case-id CASE-001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent
WEIGHTS = DATA_DIR / "weights/flow/nest/multi/cell/20x/discrete/flow_model.pth"
STATS = DATA_DIR / "statistics/nest/multi/cell/discrete/stats_table.npz"


def _require_torch_cuda() -> None:
    try:
        import torch
    except ImportError as exc:
        raise SystemExit(
            "Install PyTorch with CUDA: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124"
        ) from exc
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU not detected. PHOENIX inference requires a GPU.")


def _load_weights(device: str) -> dict[str, Any]:
    import torch

    if not WEIGHTS.is_file():
        raise SystemExit(
            f"PHOENIX weights missing at {WEIGHTS}\nRun: cd {DATA_DIR} && python fetch.py"
        )
    if not STATS.is_file():
        raise SystemExit(
            f"PHOENIX stats missing at {STATS}\nRun: cd {DATA_DIR} && python fetch.py"
        )
    state = torch.load(WEIGHTS, map_location=device, weights_only=False)
    return {"flow_state": state, "stats_path": str(STATS), "device": device}


def _try_official_pipeline(svs: Path, device: str) -> dict[str, Any] | None:
    """Return extraction dict if peng-lab/phoenix is installed; else None."""
    try:
        from phoenix.helpers.inference import FlowPipeline  # type: ignore
    except ImportError:
        return None
    # Upstream notebook wiring — agents extend when phoenix package is on PYTHONPATH.
    raise NotImplementedError(
        "Official FlowPipeline hook present but not configured in this repo. "
        "See https://github.com/peng-lab/phoenix/blob/main/phoenix_demo.ipynb"
    )


def _stub_extraction(svs: Path, case_id: str) -> dict[str, Any]:
    """Placeholder grid until full WSI tiling + FlowPipeline forward is wired."""
    import numpy as np

    n_cells = 64
    genes = ["CD8A", "CD3E", "FOXP3", "CD274", "EGFR", "TP53"]
    rng = np.random.default_rng(abs(hash(case_id)) % (2**32))
    spatial = rng.uniform(512, 4096, size=(n_cells, 2))
    matrix = rng.uniform(0, 1, size=(n_cells, len(genes))).astype(np.float32)
    return {
        "source": str(WEIGHTS),
        "slide": svs.name,
        "phoenix_slide_id": case_id,
        "study": "inferred",
        "n_cells": n_cells,
        "n_genes": len(genes),
        "genes": genes,
        "spatial": spatial,
        "matrix": matrix,
        "status": "pending_inference",
        "note": (
            "Stub output — replace with FlowPipeline forward using peng-lab/phoenix. "
            "Weights loaded successfully; implement tiling + inference per upstream README."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--svs", type=Path, required=True, help="H&E whole-slide image (.svs) or PNG preview")
    parser.add_argument("--out-dir", type=Path, required=True, help="output bundle directory")
    parser.add_argument("--case-id", help="case label (defaults to slide stem)")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    if not args.svs.is_file():
        raise SystemExit(f"Slide not found: {args.svs}")

    _require_torch_cuda()
    _load_weights(args.device)

    case_id = args.case_id or args.svs.stem.split("-01Z")[0].split(".")[0]
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    extraction = _try_official_pipeline(args.svs, args.device)
    if extraction is None:
        extraction = _stub_extraction(args.svs, case_id)

    from extract_slide_readouts import write_outputs

    slide_meta = {
        "case_submitter_id": case_id,
        "file_name": args.svs.name,
        "project_id": "USER",
    }
    summary = write_outputs(out_dir, case_id, slide_meta, extraction)
    summary["inference_mode"] = extraction.get("status", "inferred")
    if extraction.get("note"):
        summary["note"] = extraction["note"]
    (out_dir / "phoenix_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps({"case_id": case_id, "out_dir": str(out_dir), **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
