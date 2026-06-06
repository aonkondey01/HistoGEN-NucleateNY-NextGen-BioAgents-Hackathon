# How to open the Haiku Patient Explorer UI

The interactive UI is **not** the PowerPoint file. It is a web app you open in a browser.

---

## Easiest: GitHub Pages (no ports, no install)

After the deploy workflow runs on `main`:

**https://aonkondey01.github.io/PEAT-Nucleate-BIoHack-2026/**

### One-time setup (repo owner)

1. GitHub repo → **Settings** → **Pages**
2. **Build and deployment** → Source: **Deploy from a branch**
3. Branch: **`gh-pages`** · folder: **`/ (root)`** — **not `main`**
4. Save, then wait ~2 minutes (or re-run **Deploy Haiku UI to GitHub Pages** under Actions)

The workflow builds Vite output and pushes it to **`gh-pages`**. The `main` branch
holds source code and this README — it is **not** the built web app.

Wait ~2–3 minutes after the workflow completes, then open the URL above.

---

## Option 2 — Your computer (local)

Requires [Node.js](https://nodejs.org) 18+ and Python 3.

```bash
git clone https://github.com/aonkondey01/PEAT-Nucleate-BIoHack-2026.git
cd PEAT-Nucleate-BIoHack-2026
git checkout main
bash scripts/run_haiku_ui.sh
```

Open **http://localhost:5173** in Chrome or Safari.

---

## Option 3 — Cursor Cloud / Codespaces (ports)

1. Terminal:
   ```bash
   bash scripts/run_haiku_ui.sh
   ```
2. Wait for `Haiku UI → http://localhost:5173`
3. Bottom panel → **Ports** → **5173** → globe icon → Open in Browser

If Ports does not work, use **GitHub Pages** (above) or **Option 2** on your Mac/PC.

---

## PowerPoint only (no server)

Download from GitHub (no run required):

https://github.com/aonkondey01/PEAT-Nucleate-BIoHack-2026/blob/cursor/emma-research-slide-deck-5384/docs/slides/PEAT-Nucleate-Lung-TME-Deck.pptx

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Only README / repo file listing | Pages source is **`main`** — switch to branch **`gh-pages`**, folder **`/ (root)`** |
| Ports tab empty | Use GitHub Pages URL or run locally |
| `npm not found` | Install Node.js |
| Blank page on Pages | Wait for Actions workflow; hard-refresh browser |
| "Data load failed" | Re-run `python3 ui/haiku-patient-explorer/scripts/generate_representative_ui_data.py` |

---

## What you should see

- **Left:** TME spatial heatmap (changes per patient)
- **Centre:** H&E slide placeholder
- **Right:** UMAP plot with 20 representative patients — click dots to explore
