#!/usr/bin/env python3
"""Run PHOENIX virtual RNA inference on demo H&E slides (GPU required).

Expects weights from ``data/phoenix/fetch.py``. Writes bundles under
``demo/phoenix/outputs/{case_id}/`` and optionally registers coordinates onto
H&E thumbnails for the UI.

For the bundled TCGA demo without re-inference, pass ``--demo-atlas`` to subset
the precomputed AnnData instead (see ``fetch_demo_atlas.py``).

Usage:
    python scripts/demo/fetch_phoenix.py
    python scripts/demo/run_phoenix.py
    python scripts/demo/run_phoenix.py --demo-atlas
    python scripts/demo/run_phoenix.py --cases TCGA-56-5898
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHOENIX = ROOT / "data" / "phoenix"
sys.path.insert(0, str(ROOT / "demo"))
from paths import BUNDLE_ROOT, PATIENTS_JSON, PHOENIX_OUT, find_wsi  # noqa: E402


def _run_demo_atlas(case_ids: list[str], *, skip_register: bool) -> list[dict]:
    cmd = [sys.executable, str(ROOT / "scripts" / "demo" / "extract_phoenix_bundles.py")]
    if skip_register:
        cmd.append("--skip-register")
    cmd.extend(["--cases", *case_ids])
    subprocess.run(cmd, cwd=ROOT, check=True)
    return [{"case_id": cid, "mode": "demo_atlas"} for cid in case_ids]


def _run_inference(case_id: str, svs: Path, *, device: str, skip_register: bool) -> dict:
    out_dir = PHOENIX_OUT / case_id
    bundle_dir = BUNDLE_ROOT / case_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            str(PHOENIX / "inference.py"),
            "--svs",
            str(svs),
            "--out-dir",
            str(out_dir),
            "--case-id",
            case_id,
            "--device",
            device,
        ],
        cwd=PHOENIX,
        check=True,
    )

    # Copy inference outputs into the UI bundle path.
    for name in (
        "phoenix_cells.csv",
        "phoenix_gene_summary.csv",
        "phoenix_summary.json",
        "phoenix_tiles.json",
        "phoenix_spatial_heatmap.json",
    ):
        src = out_dir / name
        if src.is_file():
            (bundle_dir / name).write_bytes(src.read_bytes())

    if not skip_register:
        reg = bundle_dir / "phoenix_registration" / "phoenix_cells_registered.csv"
        if not reg.is_file():
            subprocess.run(
                [
                    sys.executable,
                    str(PHOENIX / "register_phoenix_to_he.py"),
                    "--case",
                    case_id,
                    "--svs",
                    str(svs),
                ],
                cwd=ROOT,
                check=True,
            )

    return {"case_id": case_id, "mode": "inference", "out_dir": str(out_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="*", help="subset of demo case IDs")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--demo-atlas",
        action="store_true",
        help="use precomputed TCGA AnnData subset (demo only; no GPU inference)",
    )
    parser.add_argument("--skip-register", action="store_true")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    rep = json.loads(PATIENTS_JSON.read_text())
    case_ids = args.cases or [p["case_submitter_id"] for p in rep["patients"]]
    if args.limit:
        case_ids = case_ids[: args.limit]

    PHOENIX_OUT.mkdir(parents=True, exist_ok=True)

    if args.demo_atlas:
        results = _run_demo_atlas(case_ids, skip_register=args.skip_register)
    else:
        results = []
        for case_id in case_ids:
            svs = find_wsi(case_id)
            if svs is None:
                results.append({"case_id": case_id, "error": "WSI not found — run scripts/demo/fetch_wsi.py"})
                continue
            try:
                results.append(_run_inference(case_id, svs, device=args.device, skip_register=args.skip_register))
                print(f"OK  {case_id}")
            except subprocess.CalledProcessError as err:
                results.append({"case_id": case_id, "error": str(err)})

    (PHOENIX_OUT / "run_summary.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
