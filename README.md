# PEAT-Nucleate-BIoHack-2026

## HistoTME

The upstream HistoTME repository is included as a submodule at
`external/HistoTME`.

Start with the setup guide:

```bash
git submodule update --init --recursive
./scripts/setup_histotme.sh
```

See `docs/HISTOTME_SETUP.md` for checkpoint download, TCGA slide download,
embedding generation, and inference commands.

## Haiku Patient Explorer (interactive UI)

The lung cancer TME dashboard lives in `ui/haiku-patient-explorer/`.

**Live demo (GitHub Pages):** https://aonkondey01.github.io/PEAT-Nucleate-BIoHack-2026/

Run locally:

```bash
bash scripts/run_haiku_ui.sh
# open http://localhost:5173
```

Slide deck: `docs/slides/PEAT-Nucleate-Lung-TME-Deck.pptx` — see `docs/slides/HOW_TO_OPEN_UI.md`.