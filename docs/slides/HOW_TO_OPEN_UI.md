# How to open the Haiku Patient Explorer UI

The UI is a **local web app** — it does not open from the PowerPoint file. You must run a small server, then open a link in your browser.

---

## Option 1 — Cursor Cloud (recommended if you use the agent)

1. Open the **Terminal** in Cursor (bottom of the screen).
2. Paste and run:

   ```bash
   bash /workspace/scripts/run_haiku_ui.sh
   ```

3. Wait until you see: `Local: http://localhost:5173/`
4. Open the **Ports** panel:
   - Bottom bar → click **Ports** (next to Terminal)
   - Or menu: **View → Ports**
5. Find **5173** in the list → click **Open in Browser** (globe icon).

If Ports is empty, click **Forward a Port** → enter `5173`.

---

## Option 2 — Your own computer (clone the repo)

```bash
git clone https://github.com/aonkondey01/PEAT-Nucleate-BIoHack-2026.git
cd PEAT-Nucleate-BIoHack-2026
git checkout cursor/emma-research-slide-deck-5384
bash scripts/run_haiku_ui.sh
```

Then open in Chrome/Safari/Edge: **http://localhost:5173**

Requirements: Node.js 18+ and Python 3 installed.

---

## Option 3 — Manual steps

```bash
cd ui/haiku-patient-explorer
npm install
python3 scripts/generate_demo_data.py   # first time only (~30 sec)
npm run dev
```

Open **http://localhost:5173**

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Blank page | Wait for terminal to finish; refresh browser |
| `npm: command not found` | Install Node.js from https://nodejs.org |
| Port 5173 in use | Run `npm run dev -- --port 5174` and open that port |
| "Data load failed" | Run `python3 scripts/generate_demo_data.py` inside `ui/haiku-patient-explorer` |
| No Ports tab | Use Option 2 on your local machine instead |

---

## What you should see

- **Left:** colored TME heatmap
- **Centre:** slide placeholder
- **Right:** UMAP scatter plot with ~956 dots

Click any dot to select a patient.
