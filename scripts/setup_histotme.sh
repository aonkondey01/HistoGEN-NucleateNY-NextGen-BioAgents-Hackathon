#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${1:-"$ROOT_DIR/.venv-histotme"}"
PYTHON_BIN="${PYTHON:-python3}"

if [[ ! -e "$ROOT_DIR/external/HistoTME/setup.py" ]]; then
  git -C "$ROOT_DIR" submodule update --init --recursive external/HistoTME
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$ROOT_DIR/external/HistoTME" huggingface_hub

python - <<'PY'
import h5py
import numpy
import openslide
import pandas
import timm
import torch

print("HistoTME environment ready")
print(f"torch={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
print(f"numpy={numpy.__version__}")
print(f"pandas={pandas.__version__}")
print(f"h5py={h5py.__version__}")
print(f"timm={timm.__version__}")
print(f"openslide={openslide.__version__}")
PY
