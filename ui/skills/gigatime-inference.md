# GigaTIME virtual mIF

## Fetch weights (gated)

```bash
export HF_TOKEN=...   # account must accept prov-gigatime/GigaTIME gate
cd data/gigatime
pip install -r requirements.txt
python fetch.py
```

## Demo inference (GPU required)

```bash
python scripts/demo/run_gigatime.py
# outputs → demo/gigatime/outputs/{case_id}/
```

Requires PyTorch with CUDA. Weights stay in `data/gigatime/model.pth` (gitignored).

## UI protein structures

Cached Biohub ESM Atlas structures for GigaTIME markers live in
`ui/demo_cache/gigatime_structures/`. See `ui/skills/protein-structure.md`.

## License

GigaTIME is **research-only, non-commercial** — do not commit or redistribute weights.
