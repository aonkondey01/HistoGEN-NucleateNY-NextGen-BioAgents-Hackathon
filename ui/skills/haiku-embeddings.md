# Haiku patient embeddings

Haiku combines **clinical notes** (from `demo/data_package/per_patient/*/clinical.json`),
**PHOENIX TME signatures**, and **H&E bundle metadata** into patient embeddings for
similarity search and agent chat.

## Demo build

```bash
python scripts/demo/run_haiku.py
# → demo/haiku/patients_embedding.json
```

Regenerate explorer JSON (20 patients + UMAP):

```bash
python ui/haiku-patient-explorer/scripts/generate_representative_ui_data.py
# → demo/ui/patients_embedding.json
```

## Full-cohort explorer (956 patients)

Synthetic/demo fallback when HistoTME signatures are unavailable:

```bash
cd ui/haiku-patient-explorer
python scripts/generate_demo_data.py
```

## Production

Anthropic API key for live agent chat is **not wired** in static `ui/index.html` yet;
dashboard chat remains mock stubs unless extended.
