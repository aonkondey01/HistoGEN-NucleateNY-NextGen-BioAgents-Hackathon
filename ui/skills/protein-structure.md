# Agent skill: Protein structure lookup (Biohub ESM Atlas)

## Trigger phrases

- "show me the structure of CD3E"
- "show structure CD3E"
- "show me the structure of CD19"
- "structure of {GENE}"

## Demo cache (GigaTIME markers)

Twenty GigaTIME virtual mIF protein channels (PD-1, CD3, CD8, PD-L1, Ki67, …) can be
pre-fetched from Biohub and stored under `ui/demo_cache/gigatime_structures/` for
offline live demos:

```bash
# Requires BIOHUB_API_KEY in ui/.env — run once before a demo
python scripts/cache_gigatime_structures.py
```

The UI server serves cached structures first (`USE_PROTEIN_CACHE=1` by default).
Check status: `GET /api/protein/demo-genes`.

Try in Agent Chat: `show me the structure of CD3E`, `structure CD274`, etc.

## Demo samples

| Gene | Role | UniProt | Notes |
|------|------|---------|-------|
| **CD3E** | T-cell receptor CD3 ε chain | P07766 | Immune checkpoint / TME context |
| **CD19** | B-cell surface antigen | P15391 | CAR-T / B-cell oncology target |

Try the suggestion chips in Agent Chat, or type e.g. `show me the structure of CD19`.

## Behavior

1. Parse gene symbol from the user message (e.g. `CD3E`, `CD19`).
2. Call `GET /api/protein/structure?gene=CD19` on the local UI server.
3. Render agent reply with:
   - Protein name, UniProt accession, pTM / mean pLDDT
   - Top SAE feature labels from Biohub
   - Interactive 3D cartoon (PDB from ESM Atlas)
   - Link to Biohub atlas page

## Backend flow

1. UniProt REST → canonical human sequence for gene
2. MD5(sequence) → `protein_hash`
3. Biohub `GET /esm/protein/api/v1alpha1/proteins/{hash}?fold_on_miss=true`

## Run

1. Copy `ui/.env.example` → `ui/.env` and set `BIOHUB_API_KEY` from the [Biohub developer console](https://biohub.ai/).
2. Start the server:

```bash
bash scripts/run_ui.sh
# or: cd ui && .venv/bin/python protein_server.py
```

Open http://127.0.0.1:8080 and ask in Agent Chat.

**Never commit `ui/.env` or paste API keys into chat or frontend code.**
