import "./styles.css";
import { buildEmbeddingPlot } from "./embedding.js";

const DATA_URL = `${import.meta.env.BASE_URL}data/patients_embedding.json`;

const SIGNATURES = [
  "Treg",
  "Effector_cells",
  "Macrophages",
  "CAF",
  "MDSC",
  "T_cells",
  "Checkpoint_inhibition",
  "Angiogenesis",
];

const COLOR_OPTIONS = [
  { value: "predicted_benefit", label: "Predicted benefit" },
  { value: "treatment_category", label: "Treatment class" },
  { value: "disease_response", label: "Observed response" },
  { value: "vital_status", label: "Vital status" },
  { value: "stage", label: "Stage" },
  { value: "histology", label: "Histology" },
  { value: "driver_mutation", label: "Driver mutation" },
  { value: "smoking", label: "Smoking" },
];

const app = document.querySelector("#app");

app.innerHTML = `
  <header class="top-bar">
    <div class="brand">
      <h1>Haiku Patient Explorer</h1>
      <p>TCGA lung · TME signatures · treatment &amp; benefit prediction</p>
    </div>
    <div class="controls">
      <label>
        Search
        <input id="search-input" type="search" placeholder="Patient ID or treatment…" autocomplete="off" />
      </label>
      <label>
        Color by
        <select id="color-by"></select>
      </label>
      <div class="nav-buttons">
        <button type="button" id="prev-patient" class="ghost-btn">← Prev</button>
        <button type="button" id="next-patient" class="ghost-btn">Next →</button>
      </div>
    </div>
  </header>

  <main class="layout">
    <section class="panel treatment-panel">
      <div class="panel-head">
        <h2>Treatment &amp; benefit</h2>
        <span id="treatment-patient-id" class="chip">—</span>
      </div>
      <div id="treatment-content" class="treatment-content">
        <p class="muted">Select a patient on the embedding plot.</p>
      </div>
    </section>

    <section class="panel he-panel">
      <div class="panel-head">
        <h2>H&amp;E slide</h2>
        <span class="chip muted">WSI placeholder</span>
      </div>
      <div class="he-viewport" id="he-viewport">
        <div class="he-placeholder">
          <div class="he-grid"></div>
          <p>Whole-slide image viewer</p>
          <p class="muted">Connect HistoTME tile server or OpenSlide for live H&amp;E</p>
        </div>
      </div>
    </section>

    <section class="panel right-stack">
      <div class="subpanel">
        <div class="panel-head compact">
          <h2>Patient embedding</h2>
          <span class="chip">UMAP · 8 TME signatures</span>
        </div>
        <div id="embedding-plot" class="plot-host"></div>
      </div>

      <div class="subpanel patient-card" id="patient-card">
        <p class="muted">Click a point to inspect a patient.</p>
      </div>

      <div class="subpanel">
        <div class="panel-head compact">
          <h2>Immune profile</h2>
        </div>
        <div id="immune-bars" class="immune-bars"></div>
      </div>

      <div class="subpanel">
        <div class="panel-head compact">
          <h2>Survival</h2>
        </div>
        <div id="survival-plot" class="plot-host small"></div>
      </div>
    </section>
  </main>
`;

const colorSelect = document.getElementById("color-by");
COLOR_OPTIONS.forEach((opt) => {
  const el = document.createElement("option");
  el.value = opt.value;
  el.textContent = opt.label;
  colorSelect.appendChild(el);
});

let patients = [];
let selectedId = null;
let filteredIds = null;
let colorBy = "predicted_benefit";

function splitField(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value)
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
}

function normalizePatient(p) {
  const benefit = p.predicted_benefit || {};
  const treatment = p.treatment || {};
  const clinical = p.clinical || {};
  return {
    ...p,
    patient_id: p.patient_id || p.case_id,
    driver_mutation: p.driver_mutation || p.driver || "WT",
    treatment_category: p.treatment_category || treatment.category,
    disease_response: p.disease_response || treatment.disease_response || clinical.disease_response,
    histology: p.histology || clinical.diagnosis || "Lung carcinoma",
    stage: p.stage || clinical.stage || "—",
    smoking: p.smoking || "Unknown",
    predicted_benefit: {
      ...benefit,
      rationale: benefit.rationale || benefit.reasons || [],
    },
    treatment: {
      ...treatment,
      agents: splitField(treatment.agents),
      types: splitField(treatment.types),
      regimen_summary: treatment.regimen_summary || treatment.regimen || "—",
    },
    clinical: {
      ...clinical,
      vital_status: clinical.vital_status || (p.os_status === "alive" ? "Alive" : "Dead"),
      overall_survival_days: clinical.overall_survival_days ?? clinical.survival_days,
      progression_or_recurrence: clinical.progression_or_recurrence || treatment.progression,
    },
  };
}

function getPatient(id) {
  return patients.find((p) => p.patient_id === id);
}

function getDisplayPatients() {
  if (!filteredIds) return patients;
  const set = new Set(filteredIds);
  return patients.filter((p) => set.has(p.patient_id));
}

function benefitClass(label) {
  if (!label) return "benefit-uncertain";
  if (label.includes("Likely")) return "benefit-likely";
  if (label.includes("Unlikely")) return "benefit-unlikely";
  return "benefit-uncertain";
}

function renderTreatmentPanel(patient) {
  const host = document.getElementById("treatment-content");
  const chip = document.getElementById("treatment-patient-id");
  if (!patient) {
    chip.textContent = "—";
    host.innerHTML = `<p class="muted">Select a patient on the embedding plot.</p>`;
    return;
  }

  chip.textContent = patient.patient_id;
  const t = patient.treatment || {};
  const c = patient.clinical || {};
  const b = patient.predicted_benefit || {};

  const agents = (t.agents || []).slice(0, 6);
  const agentsHtml =
    agents.length > 0
      ? agents.map((a) => `<span class="agent-pill">${a}</span>`).join("")
      : `<span class="muted">No agents recorded</span>`;

  const rationale = (b.rationale || [])
    .map((r) => `<li>${r}</li>`)
    .join("");

  host.innerHTML = `
    <div class="benefit-hero ${benefitClass(b.label)}">
      <div class="benefit-score-ring" style="--pct: ${b.score ?? 50}%">
        <span class="benefit-score-num">${b.score ?? "—"}</span>
      </div>
      <div class="benefit-hero-text">
        <div class="benefit-label">${b.label || "—"}</div>
        <div class="benefit-sub">${b.recommended_class || t.category || "—"}</div>
      </div>
    </div>

    <div class="treatment-grid">
      <div class="treatment-block">
        <h3>Treatment received</h3>
        <dl>
          <dt>Category</dt><dd>${t.category || "—"}</dd>
          <dt>Intent</dt><dd>${t.intent || "—"}</dd>
          <dt>Regimen</dt><dd>${t.regimen_summary || "—"}</dd>
          <dt>Types</dt><dd>${(t.types || []).join(", ") || "—"}</dd>
        </dl>
        <div class="agent-row">${agentsHtml}</div>
      </div>

      <div class="treatment-block">
        <h3>Observed outcome</h3>
        <dl>
          <dt>Response</dt><dd class="outcome-${(c.disease_response || "unknown").toLowerCase().replace(/\s+/g, "-")}">${c.disease_response || "—"}</dd>
          <dt>Progression</dt><dd>${c.progression_or_recurrence || "—"}</dd>
          <dt>Vital status</dt><dd>${c.vital_status || "—"}</dd>
          <dt>OS (days)</dt><dd>${c.overall_survival_days ?? "—"}</dd>
        </dl>
      </div>
    </div>

    <div class="rationale-block">
      <h3>Why this prediction?</h3>
      <ul class="rationale-list">${rationale || "<li>No rationale available</li>"}</ul>
      <p class="disclaimer muted">Demo heuristic: TME signatures + treatment class + observed response. Not clinical advice.</p>
    </div>
  `;
}

function renderPatientCard(patient) {
  const card = document.getElementById("patient-card");
  if (!patient) {
    card.innerHTML = `<p class="muted">Click a point to inspect a patient.</p>`;
    return;
  }

  const b = patient.predicted_benefit || {};
  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="patient-id">${patient.patient_id}</div>
        <div class="patient-meta">${patient.histology} · Stage ${patient.stage} · ${patient.smoking}</div>
      </div>
      <span class="benefit-badge ${benefitClass(b.label)}">${b.label || "—"}</span>
    </div>
    <div class="card-grid">
      <div><span class="label">Driver</span><strong>${patient.driver_mutation}</strong></div>
      <div><span class="label">Treatment</span><strong>${patient.treatment_category || "—"}</strong></div>
      <div><span class="label">Response</span><strong>${patient.disease_response || "—"}</strong></div>
      <div><span class="label">Benefit score</span><strong>${b.score ?? "—"}/100</strong></div>
    </div>
  `;
}

function renderImmuneBars(patient) {
  const host = document.getElementById("immune-bars");
  if (!patient) {
    host.innerHTML = "";
    return;
  }

  const maxVal = Math.max(...SIGNATURES.map((s) => patient.signatures[s] || 0), 0.01);
  host.innerHTML = SIGNATURES.map((sig) => {
    const v = patient.signatures[sig] || 0;
    const pct = Math.round((v / maxVal) * 100);
    return `
      <div class="immune-row">
        <span class="immune-label">${sig.replace(/_/g, " ")}</span>
        <div class="immune-track"><div class="immune-fill" style="width:${pct}%"></div></div>
        <span class="immune-val">${v.toFixed(2)}</span>
      </div>
    `;
  }).join("");
}

function renderSurvival(patient) {
  const host = document.getElementById("survival-plot");
  if (!patient) {
    host.innerHTML = "";
    return;
  }

  const os = patient.clinical?.overall_survival_days ?? patient.overall_survival_months * 30.44;
  const event = patient.clinical?.vital_status === "Dead" ? 1 : 0;
  const months = os / 30.44;

  const curve = [];
  for (let m = 0; m <= 60; m += 2) {
    const hazard = event ? (m > months ? 0.08 : 0.02) : 0.015;
    const prev = curve.length ? curve[curve.length - 1].s : 1;
    curve.push({ m, s: Math.max(0, prev * (1 - hazard)) });
  }

  const w = host.clientWidth || 280;
  const h = 120;
  const pad = { l: 36, r: 12, t: 12, b: 28 };
  const xScale = (m) => pad.l + (m / 60) * (w - pad.l - pad.r);
  const yScale = (s) => pad.t + (1 - s) * (h - pad.t - pad.b);

  const path = curve.map((pt, i) => `${i ? "L" : "M"}${xScale(pt.m).toFixed(1)},${yScale(pt.s).toFixed(1)}`).join(" ");
  const markerX = xScale(Math.min(months, 60));

  host.innerHTML = `
    <svg width="${w}" height="${h}" class="survival-svg">
      <line x1="${pad.l}" y1="${h - pad.b}" x2="${w - pad.r}" y2="${h - pad.b}" stroke="#cbd5e1"/>
      <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${h - pad.b}" stroke="#cbd5e1"/>
      <path d="${path}" fill="none" stroke="#0d9488" stroke-width="2"/>
      <line x1="${markerX}" y1="${pad.t}" x2="${markerX}" y2="${h - pad.b}" stroke="#f59e0b" stroke-dasharray="4,3"/>
      <text x="${pad.l}" y="${h - 6}" font-size="10" fill="#64748b">Months</text>
      <text x="4" y="${pad.t + 8}" font-size="10" fill="#64748b">S</text>
      <text x="${markerX + 4}" y="${pad.t + 14}" font-size="9" fill="#b45309">${months.toFixed(0)} mo</text>
    </svg>
    <p class="survival-caption muted">Illustrative KM · OS ${Math.round(os)} d · ${patient.clinical?.vital_status || "—"}</p>
  `;
}

function selectPatient(id) {
  if (!id || !getPatient(id)) return;
  selectedId = id;
  const patient = getPatient(id);
  renderTreatmentPanel(patient);
  renderPatientCard(patient);
  renderImmuneBars(patient);
  renderSurvival(patient);
  refreshEmbedding();
}

function refreshEmbedding() {
  const display = getDisplayPatients();
  buildEmbeddingPlot({
    container: document.getElementById("embedding-plot"),
    patients: display,
    allPatients: patients,
    colorBy,
    selectedId,
    onSelect: selectPatient,
  });
}

function applySearch(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    filteredIds = null;
    refreshEmbedding();
    return;
  }
  filteredIds = patients
    .filter((p) => {
      const blob = [
        p.patient_id,
        p.histology,
        p.driver_mutation,
        p.treatment_category,
        p.disease_response,
        p.predicted_benefit?.label,
        ...(p.treatment?.agents || []),
        ...(p.treatment?.types || []),
      ]
        .join(" ")
        .toLowerCase();
      return blob.includes(q);
    })
    .map((p) => p.patient_id);
  refreshEmbedding();
}

async function init() {
  const res = await fetch(DATA_URL);
  const raw = await res.json();
  const list = Array.isArray(raw) ? raw : raw.patients || [];
  patients = list.map(normalizePatient);
  if (patients.length) selectPatient(patients[0].patient_id);

  document.getElementById("search-input").addEventListener("input", (e) => applySearch(e.target.value));
  document.getElementById("color-by").addEventListener("change", (e) => {
    colorBy = e.target.value;
    refreshEmbedding();
  });

  document.getElementById("prev-patient").addEventListener("click", () => {
    const list = getDisplayPatients();
    const idx = list.findIndex((p) => p.patient_id === selectedId);
    const next = idx <= 0 ? list.length - 1 : idx - 1;
    if (list[next]) selectPatient(list[next].patient_id);
  });

  document.getElementById("next-patient").addEventListener("click", () => {
    const list = getDisplayPatients();
    const idx = list.findIndex((p) => p.patient_id === selectedId);
    const next = idx < 0 || idx >= list.length - 1 ? 0 : idx + 1;
    if (list[next]) selectPatient(list[next].patient_id);
  });

  window.addEventListener("resize", () => {
    if (selectedId) renderSurvival(getPatient(selectedId));
    refreshEmbedding();
  });
}

init();
