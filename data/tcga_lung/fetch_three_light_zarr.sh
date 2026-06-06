#!/usr/bin/env bash
# Download three TCGA-LUAD diagnostic slides and convert to light Zarr stores.
set -euo pipefail

cd "$(dirname "$0")"

WSI_DIR="${WSI_DIR:-./WSI}"
ZARR_DIR="${ZARR_DIR:-./zarr}"
MANIFEST="${MANIFEST:-./gdc_manifest.three_pilot.txt}"

pip3 install -q -r requirements.txt

if [[ ! -f "$MANIFEST" ]]; then
  cat > "$MANIFEST" <<'EOF'
id	filename	md5	size	state
9a077587-a524-4622-afbc-c061b91cfcaf	TCGA-44-2661-01Z-00-DX1.20cfa0f8-e3ca-4c26-9dfe-b9d416cd94b1.svs	2249ee6f90b5a79fddcb1b44aedf7fe3	544705835	released
3fdb16f9-2c00-4e03-ac66-f6cf76b4637f	TCGA-55-7815-01Z-00-DX1.288408e6-f6b3-4de4-a1ce-cb2498d9d46d.svs	dcaf98e33063b8c96569d152314ddb3c	242594627	released
78b2104d-3173-441e-8e33-46ab57f3ef42	TCGA-86-7701-01Z-00-DX1.a8a6e71e-9fa9-42c6-a186-0ac7526e9960.svs	c701e065647159d70100e7264febace8	394589659	released
EOF
fi

echo "=== Downloading 3 slides (~1.2 GB) -> ${WSI_DIR} ==="
python3 download.py --manifest "$MANIFEST" --out-dir "$WSI_DIR" --workers 4

echo "=== Converting to light Zarr -> ${ZARR_DIR} ==="
python3 svs_to_zarr.py --default-three --wsi-dir "$WSI_DIR" --out-dir "$ZARR_DIR"

echo "=== Done ==="
du -sh "$ZARR_DIR"/*.zarr
