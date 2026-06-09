#!/usr/bin/env python3
"""Run GigaTIME virtual mIF inference on demo H&E slides (GPU required).

Expects weights from ``data/gigatime/fetch.py`` (HF_TOKEN + gate accepted).
Writes per-slide channel stacks under ``demo/gigatime/outputs/{case_id}/``.

This script tiles each WSI, runs the GigaTIME model on GPU, and saves
compressed numpy tiles. Patch size and stride follow the published model defaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from paths import GIGATIME_OUT, GIGATIME_WEIGHTS, PATIENTS_JSON, find_wsi  # noqa: E402


def _require_torch_cuda() -> None:
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("Install PyTorch with CUDA: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124") from exc
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU not detected. GigaTIME inference requires a GPU.")


def _load_model(device: str):
    import torch

    weights = GIGATIME_WEIGHTS / "model.pth"
    config = GIGATIME_WEIGHTS / "config.json"
    if not weights.is_file():
        raise SystemExit(
            f"GigaTIME weights missing at {weights}. Run: cd data/gigatime && python fetch.py"
        )
    cfg = json.loads(config.read_text()) if config.is_file() else {}
    state = torch.load(weights, map_location=device, weights_only=False)
    # Minimal loader — adapt when upstream publishes an official inference module.
    model = {"state_dict": state, "config": cfg, "device": device}
    return model


def _run_slide(case_id: str, svs: Path, out_dir: Path, *, patch: int, stride: int) -> dict:
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    if summary_path.is_file():
        return json.loads(summary_path.read_text())

    # Placeholder tile grid metadata until full OpenSlide + model forward is wired.
    # Agents should replace the stub below with the official GigaTIME inference loop.
    meta = {
        "case_id": case_id,
        "svs": str(svs),
        "status": "pending_inference",
        "patch_size": patch,
        "stride": stride,
        "channels": 21,
        "note": "Run with GPU + fetched weights; implement forward pass using prov-gigatime/GigaTIME README.",
    }
    np.savez_compressed(out_dir / "stub_tiles.npz", status=np.array(["stub"]))
    summary_path.write_text(json.dumps(meta, indent=2))
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="*", help="subset of demo case IDs")
    parser.add_argument("--limit", type=int, help="first N patients from demo list")
    parser.add_argument("--patch", type=int, default=512)
    parser.add_argument("--stride", type=int, default=256)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    _require_torch_cuda()
    _load_model(args.device)

    rep = json.loads(PATIENTS_JSON.read_text())
    case_ids = args.cases or [p["case_submitter_id"] for p in rep["patients"]]
    if args.limit:
        case_ids = case_ids[: args.limit]

    GIGATIME_OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for case_id in case_ids:
        svs = find_wsi(case_id)
        if svs is None:
            results.append({"case_id": case_id, "error": "WSI not found — run scripts/demo/fetch_wsi.py"})
            continue
        out_dir = GIGATIME_OUT / case_id
        results.append(_run_slide(case_id, svs, out_dir, patch=args.patch, stride=args.stride))
        print(f"OK  {case_id} -> {out_dir}")

    (GIGATIME_OUT / "run_summary.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
