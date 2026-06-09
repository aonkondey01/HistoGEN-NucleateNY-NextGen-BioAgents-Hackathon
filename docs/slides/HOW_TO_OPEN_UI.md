# HistoGEN Advisor — one UI

```bash
bash scripts/run_ui.sh
# → http://localhost:8080
```

Single dashboard (`ui/index.html` + `ui/protein_server.py`):

- **HistoGen Advisor chat** — protein structures (Biohub cache), embedded cohort figures
- **Center viewer** — H&E + PHOENIX RNA overlay + protein mode
- **Right panel** — 20-patient cluster graph, similar patients, clinical tags

Demo data: `demo/` (20 patients, PHOENIX bundles, visual report figures).

If Cursor Ports fail:

```bash
bash scripts/start_public_ui.sh
```

There is only one UI — do not run alternate Vite explorers or duplicate dashboards.
