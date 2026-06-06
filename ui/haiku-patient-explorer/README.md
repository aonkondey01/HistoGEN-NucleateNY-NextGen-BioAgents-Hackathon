# HistoGen Explorer

Three-column UI for the HistoGen lung TME platform:

| Panel | Component |
|-------|-----------|
| **Left** | If disease recurs: predicted targeted vs immunotherapy benefit |
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

- **Click** a dot in the UMAP plot → selects patient, updates treatment panel + card
- **Search** case ID or treatment in the header (e.g. `TCGA-05`, `Cisplatin`)
- **← / →** buttons → prev/next patient
- **Color-by** dropdown → targeted @ recurrence / IO @ recurrence / preferred approach / driver / archetype

## Data

Demo JSON is generated from TCGA lung clinical metadata + HistoTME example signatures:

```bash
python3 scripts/generate_demo_data.py
# or: npm run generate-data
```

Outputs:

- `public/data/patients_embedding.json` — UMAP coordinates, TME signatures, prior treatment context, and recurrence therapy predictions

Predictions estimate benefit from **targeted therapy** (driver-driven) and **immunotherapy** (TME-driven) **if disease recurs**. Prior TCGA treatment is shown for context only. Demo heuristic — not clinical advice.
