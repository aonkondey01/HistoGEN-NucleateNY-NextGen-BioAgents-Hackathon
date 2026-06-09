#!/usr/bin/env python3
"""Extract PHOENIX readouts + contour/flow registration for the 20-patient demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ui"))
sys.path.insert(0, str(ROOT / "demo"))

from paths import PATIENTS_JSON, atlas_path  # noqa: E402
from phoenix_bootstrap import clear_phoenix_caches, ensure_phoenix_bundle  # noqa: E402


def _case_ids(limit: int | None = None) -> list[str]:
    rep = json.loads(PATIENTS_JSON.read_text())
    ids = [p["case_submitter_id"] for p in rep["patients"]]
    return ids[:limit] if limit else ids


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", nargs="*", help="Subset of TCGA case IDs")
    p.add_argument("--limit", type=int)
    p.add_argument("--skip-register", action="store_true", help="Extract only; skip contour+flow")
    args = p.parse_args()

    atlas = atlas_path()
    if not atlas.is_file():
        print(f"Atlas missing: {atlas}", file=sys.stderr)
        print("Run: python scripts/demo/fetch_demo_atlas.py", file=sys.stderr)
        return 1

    case_ids = args.cases or _case_ids(args.limit)
    ok, failed = 0, []
    for case_id in case_ids:
        print(f"\n=== {case_id} ===", flush=True)
        try:
            if ensure_phoenix_bundle(case_id, register=not args.skip_register):
                ok += 1
                print(f"  ready", flush=True)
            else:
                failed.append(case_id)
                print(f"  incomplete (missing atlas or WSI for registration)", flush=True)
        except Exception as exc:
            failed.append(case_id)
            print(f"  error: {exc}", flush=True)

    clear_phoenix_caches()
    print(f"\nPHOENIX bundles: {ok}/{len(case_ids)} ready")
    if failed:
        print("Incomplete:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
