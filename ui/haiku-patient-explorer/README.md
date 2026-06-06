# Haiku Patient Explorer

Three-column UI per the PEAT-Nucleate UX spec:

| Panel | Component |
|-------|-----------|
| **Left** | TME spatial heatmap (tile-level signature scores) |
| **Centre** | H&E slide viewer (placeholder; wire to `slide.py` thumbnails) |
| **Right** | Embedding scatter · patient card · immune profile · survival demo |

## Run the interactive UI

From repo root:

```bash
bash scripts/run_haiku_ui.sh
```

Or:

```bash
cd ui/haiku-patient-explorer
npm install
npm run dev
```

Open **http://localhost:5173**

### In Cursor Cloud

1. Run `bash scripts/run_haiku_ui.sh` in the terminal
2. Open the **Ports** tab (bottom panel)
3. Click **port 5173** → **Open in Browser**

### Interactions

- **Click** a dot in the UMAP plot → selects patient, updates heatmap + card
- **Search** case ID in the header (e.g. `TCGA-05`)
- **← / →** buttons or keyboard arrows → prev/next patient
- **Hover** heatmap tiles → signature value tooltip
- **Click** immune profile bars → switch heatmap signature
- **Color-by** dropdown → archetype / driver / signature / OS

## Data

Demo JSON is generated from the TCGA lung case list + synthetic TME signatures
(placeholder until Phoenix/GigaTIME inference is wired):

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
