import "./styles.css";
import Plotly from "plotly.js-dist-min";

const ARCHETYPE_COLORS = {
  "Immune Desert": "#4e79a7",
  "Immune Inflamed": "#e15759",
  "Myeloid/Treg-rich": "#f28e2b",
  "Stroma-high": "#76b7b2",
};

const DRIVER_COLORS = {
  EGFR: "#b07aa1",
  "KRAS G12C": "#59a14f",
  ALK: "#edc948",
  WT: "#9c755f",
};

const OS_COLORS = { alive: "#008080", deceased: "#6b7280" };

let state = {
  patients: [],
  meta: {},
  spatial: null,
  selectedCaseId: null,
  colorBy: "archetype",
  heatmapSignature: "Treg",
};

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function ramp(value, min, max) {
  const t = max === min ? 0.5 : (value - min) / (max - min);
  const r = Math.round(255 * (1 - t) + 0 * t);
  const g = Math.round(220 * (1 - t) + 80 * t);
  const b = Math.round(240 * (1 - t) + 120 * t);
  return `rgb(${r},${g},${b})`;
}

function renderShell() {
  const app = document.getElementById("app");
  app.innerHTML = `
    <header>
      <div>
        <h1>Haiku Patient Explorer</h1>
        <p>TCGA lung cohort · TME spatial heatmap + embedding explorer</p>
      </div>
      <span class="badge" id="patient-count">Loading…</span>
    </header>
    <main class="layout">
      <section class="panel" id="left-panel">
        <div class="panel-header">
          <h2>TME spatial heatmap</h2>
          <select id="heatmap-sig"></select>
        </div>
        <div class="panel-body">
          <canvas id="heatmap-canvas"></canvas>
        </div>
      </section>
      <section class="panel" id="center-panel">
        <div class="panel-header"><h2>H&amp;E slide viewer</h2></div>
        <div class="panel-body" id="slide-viewer"></div>
      </section>
      <section class="right-stack" id="right-panel">
        <div class="panel">
          <div class="panel-header">
            <h2>Patient embedding</h2>
            <select id="color-by">
              <option value="archetype">TME archetype</option>
              <option value="driver">Driver mutation</option>
              <option value="signature">HistoTME signature</option>
              <option value="os_status">Overall survival</option>
            </select>
          </div>
          <div class="panel-body">
            <div id="signature-picker-wrap" style="display:none;padding:0.4rem 0.6rem;border-bottom:1px solid var(--border)">
              <select id="scatter-signature"></select>
            </div>
            <div id="embedding-plot"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header"><h2>Patient card</h2></div>
          <div class="panel-body patient-card" id="patient-card"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h2>Immune profile</h2></div>
          <div class="panel-body signature-bars" id="immune-profile"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h2>Survival (demo)</h2></div>
          <div class="panel-body survival-placeholder" id="survival-panel"></div>
        </div>
      </section>
    </main>
  `;

  document.getElementById("color-by").addEventListener("change", (e) => {
    state.colorBy = e.target.value;
    document.getElementById("signature-picker-wrap").style.display =
      state.colorBy === "signature" ? "block" : "none";
    renderEmbedding();
  });

  document.getElementById("heatmap-sig").addEventListener("change", (e) => {
    state.heatmapSignature = e.target.value;
    drawHeatmap();
  });

  document.getElementById("scatter-signature")?.addEventListener("change", () => {
    if (state.colorBy === "signature") renderEmbedding();
  });
}

function getSelectedPatient() {
  return state.patients.find((p) => p.case_id === state.selectedCaseId) || state.patients[0];
}

function selectPatient(caseId) {
  state.selectedCaseId = caseId;
  renderPatientCard();
  renderImmuneProfile();
  renderSurvival();
  renderSlideViewer();
  renderEmbedding();
  drawHeatmap();
}

function renderPatientCard() {
  const p = getSelectedPatient();
  if (!p) return;
  document.getElementById("patient-card").innerHTML = `
    <dl>
      <dt>Case ID</dt><dd>${p.case_id}</dd>
      <dt>Project</dt><dd>${p.project_id}</dd>
      <dt>TME archetype</dt><dd>${p.archetype}</dd>
      <dt>Driver</dt><dd>${p.driver}</dd>
      <dt>OS status</dt><dd>${p.os_status}</dd>
      <dt>UMAP</dt><dd>${p.umap_x.toFixed(2)}, ${p.umap_y.toFixed(2)}</dd>
    </dl>
  `;
}

function renderImmuneProfile() {
  const p = getSelectedPatient();
  if (!p) return;
  const entries = Object.entries(p.signatures).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => Math.abs(v)), 1);
  document.getElementById("immune-profile").innerHTML = entries
    .map(([name, val]) => {
      const pct = (Math.abs(val) / max) * 100;
      return `<div class="sig-row"><span>${name}</span><div class="bar"><div class="fill" style="width:${pct}%"></div></div><span>${val.toFixed(2)}</span></div>`;
    })
    .join("");
}

function renderSurvival() {
  const p = getSelectedPatient();
  if (!p) return;
  const pct = p.os_status === "alive" ? 72 : 28;
  document.getElementById("survival-panel").innerHTML = `
    <div><strong>${p.case_id}</strong> — demo KM placeholder</div>
    <div>Status: <strong>${p.os_status}</strong></div>
    <div class="survival-bar"><span style="width:${pct}%"></span></div>
    <div style="font-size:0.7rem">Replace with TCGA survival + trial arm when clinical metadata is merged.</div>
  `;
}

function renderSlideViewer() {
  const p = getSelectedPatient();
  document.getElementById("slide-viewer").innerHTML = `
    <div class="center-placeholder">
      <div>
        <strong>${p?.case_id ?? "No patient"}</strong>
        Diagnostic H&amp;E (FFPE)<br/>
        <small>Connect <code>data/tcga_lung/WSI/</code> + <code>slide.py</code> thumbnail here</small>
      </div>
    </div>
  `;
}

function plotColors(patients) {
  if (state.colorBy === "archetype") {
    return patients.map((p) => ARCHETYPE_COLORS[p.archetype] || "#999");
  }
  if (state.colorBy === "driver") {
    return patients.map((p) => DRIVER_COLORS[p.driver] || "#999");
  }
  if (state.colorBy === "os_status") {
    return patients.map((p) => OS_COLORS[p.os_status] || "#999");
  }
  const sig = document.getElementById("scatter-signature").value;
  const vals = patients.map((p) => p.signatures[sig] ?? 0);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  return vals.map((v) => ramp(v, min, max));
}

function renderEmbedding() {
  const patients = state.patients;
  const selected = state.selectedCaseId;
  const colors = plotColors(patients);
  const sizes = patients.map((p) => (p.case_id === selected ? 14 : 7));
  const lineWidths = patients.map((p) => (p.case_id === selected ? 2 : 0.5));

  const trace = {
    x: patients.map((p) => p.umap_x),
    y: patients.map((p) => p.umap_y),
    text: patients.map((p) => p.case_id),
    mode: "markers",
    type: "scattergl",
    marker: {
      color: colors,
      size: sizes,
      line: { color: "#111", width: lineWidths },
      opacity: 0.85,
    },
    hovertemplate: "%{text}<extra></extra>",
  };

  const layout = {
    margin: { l: 36, r: 12, t: 12, b: 36 },
    paper_bgcolor: "white",
    plot_bgcolor: "#fafbfc",
    xaxis: { title: "UMAP 1", zeroline: false, gridcolor: "#eceff4" },
    yaxis: { title: "UMAP 2", zeroline: false, gridcolor: "#eceff4" },
    showlegend: false,
  };

  Plotly.react("embedding-plot", [trace], layout, { responsive: true, displayModeBar: false });

  const plot = document.getElementById("embedding-plot");
  plot.on("plotly_click", (ev) => {
    const idx = ev.points?.[0]?.pointIndex;
    if (idx != null) selectPatient(patients[idx].case_id);
  });
}

function drawHeatmap() {
  const canvas = document.getElementById("heatmap-canvas");
  const parent = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;
  const w = parent.clientWidth;
  const h = parent.clientHeight;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0, 0, w, h);

  const tiles = state.spatial?.tiles || [];
  const sig = state.heatmapSignature;
  if (!tiles.length) {
    ctx.fillStyle = "#6b7280";
    ctx.font = "13px DM Sans";
    ctx.fillText("No spatial data", 20, 30);
    return;
  }

  const xs = tiles.map((t) => t.x);
  const ys = tiles.map((t) => t.y);
  const vals = tiles.map((t) => t[sig] ?? 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const minV = Math.min(...vals);
  const maxV = Math.max(...vals);
  const pad = 12;
  const scaleX = (w - pad * 2) / (maxX - minX || 1);
  const scaleY = (h - pad * 2) / (maxY - minY || 1);
  const tileW = Math.max(2, scaleX * 512 * 0.95);
  const tileH = Math.max(2, scaleY * 512 * 0.95);

  tiles.forEach((t, i) => {
    const px = pad + (t.x - minX) * scaleX;
    const py = pad + (t.y - minY) * scaleY;
    ctx.fillStyle = ramp(vals[i], minV, maxV);
    ctx.fillRect(px, py, tileW, tileH);
  });

  const p = getSelectedPatient();
  ctx.fillStyle = "#003366";
  ctx.font = "600 11px DM Sans";
  ctx.fillText(`${p?.case_id} · ${sig}`, pad, h - pad);
}

async function loadData() {
  const [embRes, spatialRes] = await Promise.all([
    fetch("/data/patients_embedding.json"),
    fetch("/data/spatial_heatmap_demo.json"),
  ]);
  const embedding = await embRes.json();
  state.patients = embedding.patients;
  state.meta = embedding.meta;
  state.spatial = await spatialRes.json();
  state.selectedCaseId = state.patients[0]?.case_id;

  document.getElementById("patient-count").textContent = `${state.patients.length} patients`;

  const heatSel = document.getElementById("heatmap-sig");
  heatSel.innerHTML = state.meta.color_signatures
    .map((s) => `<option value="${s}">${s}</option>`)
    .join("");

  const scatterSig = document.getElementById("scatter-signature");
  scatterSig.innerHTML = state.meta.color_signatures
    .map((s) => `<option value="${s}">${s}</option>`)
    .join("");

  selectPatient(state.selectedCaseId);
  window.addEventListener("resize", () => drawHeatmap());
}

renderShell();
loadData().catch((err) => {
  console.error(err);
  document.getElementById("patient-count").textContent = "Data load failed — run npm run generate-data";
});
