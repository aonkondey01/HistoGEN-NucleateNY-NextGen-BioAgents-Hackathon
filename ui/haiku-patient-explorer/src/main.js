import "./styles.css";
import Plotly from "plotly.js-dist-min";
import { generateSpatialTiles, SIGNATURES } from "./spatial.js";

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
  searchQuery: "",
  hoverTile: null,
};

function ramp(value, min, max) {
  const t = max === min ? 0.5 : (value - min) / (max - min);
  const r = Math.round(255 * (1 - t));
  const g = Math.round(220 * (1 - t) + 80 * t);
  const b = Math.round(240 * (1 - t) + 120 * t);
  return `rgb(${r},${g},${b})`;
}

function renderShell() {
  const app = document.getElementById("app");
  app.innerHTML = `
    <header>
      <div>
        <h1>HistoGEN</h1>
        <p>20 TCGA lung patients · PHOENIX virtual spatial RNA · H&amp;E</p>
      </div>
      <div class="header-actions">
        <input id="patient-search" type="search" placeholder="Search case ID…" />
        <span class="badge" id="patient-count">Loading…</span>
      </div>
    </header>
    <main class="layout">
      <section class="panel" id="left-panel">
        <div class="panel-header">
          <h2>PHOENIX spatial RNA</h2>
          <select id="heatmap-sig"></select>
        </div>
        <div class="panel-body heatmap-wrap">
          <canvas id="heatmap-canvas"></canvas>
          <div id="heatmap-tooltip" class="heatmap-tooltip hidden"></div>
          <div id="heatmap-legend" class="legend"></div>
        </div>
        <div class="panel-footer">
          <button type="button" id="prev-patient" title="Previous patient">← Prev</button>
          <span id="selected-label">—</span>
          <button type="button" id="next-patient" title="Next patient">Next →</button>
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
              <option value="signature">TME signature</option>
              <option value="os_status">Overall survival</option>
            </select>
          </div>
          <div class="panel-body">
            <div id="signature-picker-wrap" class="sig-picker-wrap hidden">
              <select id="scatter-signature"></select>
            </div>
            <div id="scatter-legend" class="scatter-legend"></div>
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
          <div class="panel-header"><h2>Clinical status</h2></div>
          <div class="panel-body survival-placeholder" id="survival-panel"></div>
        </div>
      </section>
    </main>
  `;

  document.getElementById("color-by").addEventListener("change", (e) => {
    state.colorBy = e.target.value;
    document.getElementById("signature-picker-wrap").classList.toggle("hidden", state.colorBy !== "signature");
    renderEmbedding();
    renderScatterLegend();
  });

  document.getElementById("heatmap-sig").addEventListener("change", (e) => {
    state.heatmapSignature = e.target.value;
    drawHeatmap();
    renderHeatmapLegend();
  });

  document.getElementById("scatter-signature")?.addEventListener("change", () => {
    if (state.colorBy === "signature") {
      renderEmbedding();
      renderScatterLegend();
    }
  });

  document.getElementById("patient-search").addEventListener("input", (e) => {
    state.searchQuery = e.target.value.trim().toUpperCase();
    renderEmbedding();
    const match = state.patients.find((p) => p.case_id.includes(state.searchQuery));
    if (match && state.searchQuery.length >= 6) selectPatient(match.case_id, false);
  });

  document.getElementById("prev-patient").addEventListener("click", () => stepPatient(-1));
  document.getElementById("next-patient").addEventListener("click", () => stepPatient(1));

  const canvas = document.getElementById("heatmap-canvas");
  canvas.addEventListener("mousemove", onHeatmapHover);
  canvas.addEventListener("mouseleave", () => {
    state.hoverTile = null;
    document.getElementById("heatmap-tooltip").classList.add("hidden");
  });
  canvas.addEventListener("click", onHeatmapClick);

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea")) return;
    if (e.key === "ArrowLeft") stepPatient(-1);
    if (e.key === "ArrowRight") stepPatient(1);
  });
}

function getSelectedPatient() {
  return state.patients.find((p) => p.case_id === state.selectedCaseId) || state.patients[0];
}

function getPatientIndex() {
  return state.patients.findIndex((p) => p.case_id === state.selectedCaseId);
}

function stepPatient(delta) {
  const idx = getPatientIndex();
  if (idx < 0) return;
  const next = (idx + delta + state.patients.length) % state.patients.length;
  selectPatient(state.patients[next].case_id);
}

async function refreshSpatialForPatient(patient) {
  const caseId = patient.case_id;
  const url = `/data/spatial_heatmap_${caseId}.json`;
  try {
    const res = await fetch(url);
    if (res.ok) {
      state.spatial = await res.json();
      return;
    }
  } catch {
    /* fallback below */
  }
  state.spatial = generateSpatialTiles(patient);
}

async function selectPatient(caseId, panEmbedding = true) {
  state.selectedCaseId = caseId;
  const p = getSelectedPatient();
  await refreshSpatialForPatient(p);
  renderPatientCard();
  renderImmuneProfile();
  renderSurvival();
  renderSlideViewer();
  renderEmbedding(panEmbedding);
  drawHeatmap();
  renderHeatmapLegend();
  document.getElementById("selected-label").textContent = caseId;
  document.getElementById("patient-search").value = caseId;
}

function renderPatientCard() {
  const p = getSelectedPatient();
  if (!p) return;
  document.getElementById("patient-card").innerHTML = `
    <dl>
      <dt>Case ID</dt><dd>${p.case_id}</dd>
      <dt>Project</dt><dd>${p.project_id}</dd>
      <dt>TME archetype</dt><dd><span class="pill" style="background:${ARCHETYPE_COLORS[p.archetype]}22;color:${ARCHETYPE_COLORS[p.archetype]}">${p.archetype}</span></dd>
      <dt>Driver</dt><dd><span class="pill" style="background:${DRIVER_COLORS[p.driver]}22;color:${DRIVER_COLORS[p.driver]}">${p.driver}</span></dd>
      <dt>OS status</dt><dd>${p.os_status}</dd>
      <dt>UMAP</dt><dd>${p.umap_x.toFixed(2)}, ${p.umap_y.toFixed(2)}</dd>
    </dl>
    <p class="hint">Click embedding dots · hover heatmap tiles · ← → to navigate</p>
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
      const active = name === state.heatmapSignature ? " active" : "";
      return `<button type="button" class="sig-row sig-btn${active}" data-sig="${name}">
        <span>${name}</span>
        <div class="bar"><div class="fill" style="width:${pct}%"></div></div>
        <span>${val.toFixed(2)}</span>
      </button>`;
    })
    .join("");

  document.querySelectorAll(".sig-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.heatmapSignature = btn.dataset.sig;
      document.getElementById("heatmap-sig").value = state.heatmapSignature;
      drawHeatmap();
      renderHeatmapLegend();
      renderImmuneProfile();
    });
  });
}

function renderSurvival() {
  const p = getSelectedPatient();
  if (!p) return;
  document.getElementById("survival-panel").innerHTML = `
    <div><strong>${p.case_id}</strong></div>
    <div>Vital status: <strong>${p.os_status}</strong></div>
    <div>Driver: <strong>${p.driver}</strong> · Archetype: <strong>${p.archetype}</strong></div>
    <p class="hint">OS from TCGA clinical metadata only — no modeled survival curves.</p>
  `;
}

function renderSlideViewer() {
  const p = getSelectedPatient();
  const caseId = p?.case_id ?? "";
  const thumbUrl = `/data/slides/${caseId}.thumbnail.png`;
  const hue = hashHue(caseId);
  document.getElementById("slide-viewer").innerHTML = `
    <div class="slide-viewer-wrap">
      <img class="slide-thumb" src="${thumbUrl}" alt="H&E ${caseId}"
        onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
      <div class="slide-mock" style="--hue:${hue}; display:none;">
        <div class="slide-mock-inner">
          <strong>${caseId || "No patient"}</strong>
          <span>Diagnostic H&E thumbnail not built yet</span>
          <small>Run <code>scripts/build_representative_ui_assets.py</code></small>
        </div>
      </div>
      <div class="slide-caption">${caseId} · diagnostic H&E</div>
    </div>
  `;
}

function hashHue(str) {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) h = (h * 31 + str.charCodeAt(i)) % 360;
  return h;
}

function filteredPatients() {
  if (!state.searchQuery) return state.patients;
  return state.patients.filter((p) => p.case_id.includes(state.searchQuery));
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

function renderScatterLegend() {
  const el = document.getElementById("scatter-legend");
  if (state.colorBy === "archetype") {
    el.innerHTML = Object.entries(ARCHETYPE_COLORS)
      .map(([k, c]) => `<span class="legend-chip"><i style="background:${c}"></i>${k}</span>`)
      .join("");
  } else if (state.colorBy === "driver") {
    el.innerHTML = Object.entries(DRIVER_COLORS)
      .map(([k, c]) => `<span class="legend-chip"><i style="background:${c}"></i>${k}</span>`)
      .join("");
  } else if (state.colorBy === "os_status") {
    el.innerHTML = Object.entries(OS_COLORS)
      .map(([k, c]) => `<span class="legend-chip"><i style="background:${c}"></i>${k}</span>`)
      .join("");
  } else {
    el.innerHTML = `<span class="legend-chip">Continuous: ${document.getElementById("scatter-signature").value}</span>
      <span class="legend-gradient"></span>`;
  }
}

function renderHeatmapLegend() {
  const el = document.getElementById("heatmap-legend");
  el.innerHTML = `
    <div class="legend-title">${state.heatmapSignature}</div>
    <div class="legend-gradient-bar"></div>
    <div class="legend-scale"><span>low</span><span>high</span></div>
  `;
}

function renderEmbedding(panToSelected = false) {
  const patients = filteredPatients();
  const allPatients = state.patients;
  const selected = state.selectedCaseId;
  const colors = plotColors(patients);
  const sizes = patients.map((p) => (p.case_id === selected ? 16 : 6));
  const opacity = patients.map((p) => (p.case_id === selected ? 1 : 0.55));

  const trace = {
    x: patients.map((p) => p.umap_x),
    y: patients.map((p) => p.umap_y),
    text: patients.map(
      (p) => `${p.case_id}<br>${p.archetype}<br>${p.driver}<br>OS: ${p.os_status}`,
    ),
    customdata: patients.map((p) => p.case_id),
    mode: "markers",
    type: "scattergl",
    marker: {
      color: colors,
      size: sizes,
      line: { color: "#111", width: patients.map((p) => (p.case_id === selected ? 2 : 0)) },
      opacity,
    },
    hovertemplate: "%{text}<extra></extra>",
  };

  const sel = allPatients.find((p) => p.case_id === selected);
  const traces = [trace];
  if (sel && patients.some((p) => p.case_id === selected)) {
    traces.push({
      x: [sel.umap_x],
      y: [sel.umap_y],
      mode: "markers",
      type: "scattergl",
      marker: { size: 22, color: "rgba(0,0,0,0)", line: { color: "#003366", width: 3 } },
      hoverinfo: "skip",
      showlegend: false,
    });
  }

  const layout = {
    margin: { l: 40, r: 8, t: 8, b: 36 },
    paper_bgcolor: "white",
    plot_bgcolor: "#fafbfc",
    xaxis: { title: "UMAP 1", zeroline: false, gridcolor: "#eceff4" },
    yaxis: { title: "UMAP 2", zeroline: false, gridcolor: "#eceff4" },
    showlegend: false,
    dragmode: "zoom",
  };

  Plotly.react("embedding-plot", traces, layout, { responsive: true, displayModeBar: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] });

  const plot = document.getElementById("embedding-plot");
  plot.on("plotly_click", (ev) => {
    const caseId = ev.points?.[0]?.customdata;
    if (caseId) selectPatient(caseId);
  });

  if (panToSelected && sel) {
    Plotly.relayout("embedding-plot", {
      "xaxis.range": [sel.umap_x - 1.2, sel.umap_x + 1.2],
      "yaxis.range": [sel.umap_y - 1.2, sel.umap_y + 1.2],
    });
  }
}

function heatmapLayout() {
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
  return { ctx, w, h, canvas };
}

function drawHeatmap() {
  const { ctx, w, h } = heatmapLayout();
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0, 0, w, h);

  const tiles = state.spatial?.tiles || [];
  const sig = state.heatmapSignature;
  if (!tiles.length) return;

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
  const tileW = Math.max(3, scaleX * 512 * 0.96);
  const tileH = Math.max(3, scaleY * 512 * 0.96);

  state._heatmapGeom = { tiles, minX, maxX, minY, maxY, scaleX, scaleY, tileW, tileH, pad, minV, maxV };

  tiles.forEach((t, i) => {
    const px = pad + (t.x - minX) * scaleX;
    const py = pad + (t.y - minY) * scaleY;
    ctx.fillStyle = ramp(vals[i], minV, maxV);
    ctx.fillRect(px, py, tileW, tileH);
  });

  const p = getSelectedPatient();
  const src = state.spatial?.source || "procedural";
  ctx.fillStyle = "#003366";
  ctx.font = "600 11px DM Sans";
  ctx.fillText(`${p?.case_id} · ${sig} · ${src}`, pad, h - pad);
}

function onHeatmapHover(ev) {
  const g = state._heatmapGeom;
  if (!g) return;
  const rect = ev.target.getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  const tip = document.getElementById("heatmap-tooltip");

  let hit = null;
  for (const t of g.tiles) {
    const px = g.pad + (t.x - g.minX) * g.scaleX;
    const py = g.pad + (t.y - g.minY) * g.scaleY;
    if (x >= px && x <= px + g.tileW && y >= py && y <= py + g.tileH) {
      hit = t;
      break;
    }
  }

  if (!hit) {
    tip.classList.add("hidden");
    return;
  }

  const sig = state.heatmapSignature;
  tip.classList.remove("hidden");
  tip.style.left = `${x + 12}px`;
  tip.style.top = `${y + 12}px`;
  tip.innerHTML = `<strong>(${hit.x}, ${hit.y})</strong><br>${sig}: ${(hit[sig] ?? 0).toFixed(3)}`;
}

function onHeatmapClick(ev) {
  const g = state._heatmapGeom;
  if (!g) return;
  const rect = ev.target.getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  for (const t of g.tiles) {
    const px = g.pad + (t.x - g.minX) * g.scaleX;
    const py = g.pad + (t.y - g.minY) * g.scaleY;
    if (x >= px && x <= px + g.tileW && y >= py && y <= py + g.tileH) {
      const sig = state.heatmapSignature;
      document.getElementById("heatmap-tooltip").innerHTML =
        `<strong>Tile pinned</strong><br>(${t.x}, ${t.y}) · ${sig}: ${(t[sig] ?? 0).toFixed(3)}`;
      break;
    }
  }
}

async function loadData() {
  const embRes = await fetch("/data/patients_embedding.json");
  const embedding = await embRes.json();
  state.patients = embedding.patients;
  state.meta = embedding.meta;
  state.selectedCaseId = state.patients[0]?.case_id;

  document.getElementById("patient-count").textContent = `${state.patients.length} patients`;

  const opts = (state.meta.color_signatures || SIGNATURES)
    .map((s) => `<option value="${s}">${s}</option>`)
    .join("");
  document.getElementById("heatmap-sig").innerHTML = opts;
  document.getElementById("scatter-signature").innerHTML = opts;

  selectPatient(state.selectedCaseId, false);
  renderScatterLegend();
  window.addEventListener("resize", () => drawHeatmap());
}

renderShell();
loadData().catch((err) => {
  console.error(err);
  document.getElementById("patient-count").textContent = "Data load failed — run: npm run generate-data";
});
