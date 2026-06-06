# Haiku Patient Explorer

Three-column UI per the PEAT-Nucleate UX spec:

| Panel | Component |
|-------|-----------|
| **Left** | TME spatial heatmap (tile-level signature scores) |
| **Centre** | H&E slide viewer (placeholder; wire to `slide.py` thumbnails) |
| **Right** | Embedding scatter · patient card · immune profile · survival demo |

## Run locally

```bash
cd ui/haiku-patient-explorer
npm install
npm run dev
```

Open http://localhost:5173

## Data

Demo JSON is generated from TCGA lung case list + HistoTME example signatures:

```bash
python3 scripts/generate_demo_data.py
# or: npm run generate-data
```

Outputs:

- `public/data/patients_embedding.json` — UMAP coordinates + archetype / driver / signatures
- `public/data/spatial_heatmap_demo.json` — tile heatmap for selected patient

Replace spatial JSON with real `predict_spatial.py` output when available.

## Branch

Commit UI work to `cursor/emma-research-slide-deck-5384`.
