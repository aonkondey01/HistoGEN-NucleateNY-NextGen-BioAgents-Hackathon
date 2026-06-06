# Cursor UI Iteration Prompt — SpatialMTB

## Project context

**SpatialMTB** is a clinical AI tool for head and neck oncology. It takes one routine H&E slide and a short clinical note, uses pretrained H&E foundation models to infer virtual spatial transcriptomics and multiplex protein imaging, retrieves similar prior patients with known outcomes, and generates a ranked, citation-backed virtual molecular tumor board (vMTB) report.

The core insight: mutations don't act alone. Response to therapy depends on the tumor microenvironment — whether T cells enter tumor nests, whether macrophages dominate, whether the tumor is hypoxic, stromal, HPV-like, or immune-excluded. Instead of asking "what drug matches this mutation?", SpatialMTB asks **"what kind of tumor ecosystem is this patient in, and how did similar patients behave before?"**

Primary cancer type: **head and neck squamous cell carcinoma (HNSCC)**, including HPV+ and HPV− subtypes.

---

## Current UI

The working file is `ui/index.html` — a single-file dark-theme dashboard with 4 panels:

1. **Left — Agent Chat**: Claude-powered conversational interface for the oncologist
2. **Center — H&E / Spatial Viewer**: Modality toggle (H&E / RNA / Protein) + gene/protein dropdown + drag-drop slide loader
3. **Right — Patient Cluster & Clinical**: Haiku-assigned cluster card, nearest similar patients, "Derive Clinical Outcomes" button that reveals plot placeholders
4. **Top bar**: Patient ID, cancer type badge, analysis status

The stack is intentionally **vanilla HTML/CSS/JS** (no framework) so it can be ported to React/Next.js later. Keep it that way unless you are explicitly told to switch.

---

## What to improve — prioritized list

### 1. Visual polish (highest priority)
- Make the layout feel like a premium medical SaaS (reference: [Chan Zuckerberg Biohub protein atlas](https://biohub.ai/esm/protein/atlas), Viz.bio, PathAI)
- The H&E viewer panel should feel like a real WSI viewer: add a minimap thumbnail in the bottom-right corner of the viewer, crosshair cursor on hover, tile grid overlay toggle
- Add subtle animated gradient borders or glow on the active panel
- Typography: use Inter or DM Sans; make headings crisper

### 2. Panel 1 — Agent Chat
- Add a "Clinical Note" intake section at the top of the chat panel — a small collapsible textarea where the oncologist pastes a brief clinical summary before analysis begins
- Add a typing indicator (three dots) while the agent "responds"
- Differentiate agent message types visually: plain explanation vs. cited finding (show a small citation pill, e.g. `[TCGA 2023]`) vs. warning/flag (amber left border)
- Show a "Sources" expandable footer on agent messages that cite literature

### 3. Panel 2 — Spatial Viewer
- The modality toggle + gene dropdown should feel more cohesive: when "RNA" or "Protein" is selected, animate the colorbar in from the bottom
- Add a second dropdown for **TME phenotype overlay**: options like `Immune-Hot`, `Immune-Excluded`, `Stromal-Rich`, `Hypoxic`, `HPV-like` — these would color spatial regions by predicted phenotype
- Add spot annotation: clicking a region in the viewer should pop a small tooltip showing predicted cell type composition (% tumor, % CD8+ T, % macrophage, % stroma) — use mock data for now
- Add a scale bar (e.g. "200 µm") in the bottom-left of the viewer

### 4. Panel 3 — Patient Cluster & Clinical
- Rename panel header to **"vMTB Report"** (virtual Molecular Tumor Board)
- The cluster card should show the **TME phenotype name** prominently (e.g. "Immune-Excluded, HPV−") rather than just a number
- Add a small radar/spider chart (5 axes: T-cell infiltration, Macrophage burden, Stromal density, Hypoxia score, HPV signature) using Canvas or a lightweight charting lib
- The "Derive Clinical Characteristics & Outcomes" button should be renamed **"Generate vMTB Report"**
- Replace the 3 plot placeholders with properly labeled empty chart containers:
  - Kaplan–Meier Overall Survival (similar patients vs. cluster average)
  - Treatment response waterfall plot (best response by treatment arm)
  - UMAP of patient embedding space with this patient highlighted
- Add a **"Export Report (PDF)"** button stub below the plots

### 5. Top bar
- Add an HPV status badge (HPV+ / HPV− / Unknown) next to the cancer type
- Add a small "Run Analysis" button (primary CTA) that triggers a loading shimmer across all panels

### 6. New: vMTB Report panel (optional stretch)
- Consider a 5th collapsible panel that slides up from the bottom (like a drawer) containing the full text vMTB report: ranked therapeutic options with citations, TME interpretation paragraph, and recommended biomarker confirmations
- This drawer opens when "Generate vMTB Report" is clicked

---

## Constraints

- Keep it a single HTML file (`ui/index.html`) unless refactoring to a proper frontend project
- No external JS framework dependencies unless you add a build step and update the README
- Chart libraries allowed: Chart.js (CDN), Plotly.js (CDN), or D3 (CDN) — pick one and be consistent
- Color palette: keep the dark theme (`#0d0f14` background, `#4f8ef7` accent blue, `#3ecf8e` green, `#7c5cbf` purple accent) — these are the brand colors
- Do not change the 4-panel grid layout structure — only refine within each panel
- All mock data is fine for now; add TODO comments where real API calls will go

---

## Voice & tone for agent messages

The agent is a knowledgeable but direct clinical AI. It:
- Leads with the finding, not the caveat
- Cites evidence when making a therapeutic claim (`[KEYNOTE-048, 2019]`)
- Flags uncertainty explicitly ("Low confidence — fewer than 5 similar patients in cohort")
- Never says "I think" — says "The spatial pattern suggests…" or "Evidence from similar patients indicates…"

Sample messages to use as stubs in the chat:
- *"The TME phenotype for this patient is Immune-Excluded, HPV−. CD8+ T cells are present in the stroma but fail to penetrate tumor nests — a pattern associated with resistance to PD-1 monotherapy."*
- *"3 of 4 nearest cluster patients responded to cetuximab + pembrolizumab combination. Median PFS: 8.2 months. [Burtness et al., KEYNOTE-048]*"
- *"⚠ Low stromal PDGFR signal — anti-angiogenic combination may be less effective for this ecosystem type."*
