import "./styles.css";
import { buildEmbeddingPlot } from "./embedding.js";

const DATA_URL = `${import.meta.env.BASE_URL}data/patients_embedding.json`;
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "0";

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
  { value: "targeted_benefit", label: "Targeted therapy (at recurrence)" },
  { value: "immunotherapy_benefit", label: "Immunotherapy (at recurrence)" },
  { value: "preferred_at_recurrence", label: "Preferred at recurrence" },
  { value: "driver_mutation", label: "Driver mutation" },
  { value: "archetype", label: "TME archetype" },
  { value: "treatment_category", label: "Prior treatment class" },
  { value: "disease_response", label: "Observed response" },
  { value: "stage", label: "Stage" },
];

const app = document.querySelector("#app");

app.innerHTML = `
  <header class="top-bar">
    <div class="brand">
      <div>
      <h1>HistoGEN</h1>
      <p>Lung TME · predict targeted / immunotherapy benefit if disease recurs</p>
      </div>
    </div>
    <div class="controls">
      <label>
        Search
        <input id="search-input" type="search" placeholder="Patient ID, driver, therapy…" autocomplete="off" />
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
        <h2>Recurrence therapy predictions</h2>
        <span id="treatment-patient-id" class="chip">—</span>
      </div>
      <div id="treatment-content" class="treatment-content">
        <p class="muted">Select a patient on the embedding plot.</p>
      </div>
    </section>

    <section class="panel he-panel">
      <div class="panel-head">
        <h2>H&amp;E slide</h2>
        <span class="chip muted">${DEMO_MODE ? "Demo WSI" : "WSI placeholder"}</span>
      </div>
      <div class="he-viewport" id="he-viewport">
        <div class="he-placeholder">
          <div class="he-grid"></div>
          <p>Whole-slide image viewer</p>
          <p class="muted">${DEMO_MODE ? "Loading demo H&amp;E preview…" : "Connect OpenSlide tile server for live H&amp;E"}</p>
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
let colorBy = "targeted_benefit";

function splitField(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value)
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
}

function normalizePatient(p) {
  const recurrence = p.recurrence_predictions || {};
  const targeted = recurrence.targeted_therapy || {};
  const immunotherapy = recurrence.immunotherapy || {};
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
    recurrence_predictions: {
      scenario: recurrence.scenario || "If disease recurs",
      preferred_at_recurrence: recurrence.preferred_at_recurrence || "—",
      targeted_therapy: {
        ...targeted,
        rationale: targeted.rationale || targeted.reasons || [],
      },
      immunotherapy: {
        ...immunotherapy,
        rationale: immunotherapy.rationale || immunotherapy.reasons || [],
      },
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

function renderTherapyCard(title, therapy, detailLabel, detailValue, cssClass) {
  const rationale = (therapy.rationale || [])
    .map((r) => `<li>${r}</li>`)
    .join("");

  return `
    <div class="therapy-card ${cssClass} ${benefitClass(therapy.label)}">
      <div class="therapy-card-head">
        <h3>${title}</h3>
        <span class="benefit-badge ${benefitClass(therapy.label)}">${therapy.label || "—"}</span>
      </div>
      <div class="therapy-score-row">
        <div class="benefit-score-ring small" style="--pct: ${therapy.score ?? 50}%">
          <span class="benefit-score-num">${therapy.score ?? "—"}</span>
        </div>
        <div class="therapy-rec">
          <span class="rec-label">${detailLabel}</span>
          <strong>${detailValue || "—"}</strong>
        </div>
      </div>
      <ul class="rationale-list compact">${rationale || "<li>No rationale available</li>"}</ul>
    </div>
  `;
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
  const r = patient.recurrence_predictions || {};
  const targeted = r.targeted_therapy || {};
  const immuno = r.immunotherapy || {};

  const agents = (t.agents || []).slice(0, 5);
  const agentsHtml =
    agents.length > 0
      ? agents.map((a) => `<span class="agent-pill">${a}</span>`).join("")
      : `<span class="muted">No agents recorded</span>`;

  host.innerHTML = `
    <p class="scenario-banner">${r.scenario || "If disease recurs"}</p>
    <div class="preferred-banner">
      <span>Preferred approach</span>
      <strong>${r.preferred_at_recurrence || "—"}</strong>
    </div>

    <div class="therapy-grid">
      ${renderTherapyCard(
        "Targeted therapy",
        targeted,
        "Suggested agents",
        targeted.recommended_agents,
        "therapy-targeted",
      )}
      ${renderTherapyCard(
        "Immunotherapy",
        immuno,
        "Suggested regimen",
        immuno.recommended_regimen,
        "therapy-immuno",
      )}
    </div>

    <div class="treatment-grid">
      <div class="treatment-block">
        <h3>Prior treatment (context)</h3>
        <dl>
          <dt>Category</dt><dd>${t.category || "—"}</dd>
          <dt>Intent</dt><dd>${t.intent || "—"}</dd>
          <dt>Types</dt><dd>${(t.types || []).join(", ") || "—"}</dd>
        </dl>
        <div class="agent-row">${agentsHtml}</div>
      </div>

      <div class="treatment-block">
        <h3>Current status</h3>
        <dl>
          <dt>Response</dt><dd>${c.disease_response || "—"}</dd>
          <dt>Progression</dt><dd>${c.progression_or_recurrence || "—"}</dd>
          <dt>Vital status</dt><dd>${c.vital_status || "—"}</dd>
          <dt>Driver</dt><dd>${patient.driver_mutation}</dd>
        </dl>
      </div>
    </div>

    <p class="disclaimer muted">Demo heuristic: driver mutation + TME archetype + PHOENIX signatures. Predicts benefit at recurrence, not current adjuvant therapy. Not clinical advice.</p>
  `;
}

function renderPatientCard(patient) {
  const card = document.getElementById("patient-card");
  if (!patient) {
    card.innerHTML = `<p class="muted">Click a point to inspect a patient.</p>`;
    return;
  }

  const targeted = patient.recurrence_predictions?.targeted_therapy || {};
  const immuno = patient.recurrence_predictions?.immunotherapy || {};

  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="patient-id">${patient.patient_id}</div>
        <div class="patient-meta">${patient.archetype} · ${patient.driver_mutation} · Stage ${patient.stage}</div>
      </div>
    </div>
    <div class="card-grid">
      <div><span class="label">Targeted @ recurrence</span><strong class="${benefitClass(targeted.label)}">${targeted.label || "—"} (${targeted.score ?? "—"})</strong></div>
      <div><span class="label">IO @ recurrence</span><strong class="${benefitClass(immuno.label)}">${immuno.label || "—"} (${immuno.score ?? "—"})</strong></div>
      <div><span class="label">Preferred</span><strong>${patient.recurrence_predictions?.preferred_at_recurrence || "—"}</strong></div>
      <div><span class="label">Prior tx</span><strong>${patient.treatment_category || "—"}</strong></div>
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

function renderHeSlide(patient) {
  const host = document.getElementById("he-viewport");
  if (!patient) {
    host.innerHTML = `<div class="he-placeholder"><p class="muted">Select a patient.</p></div>`;
    return;
  }

  if (DEMO_MODE && patient.has_slide_preview && patient.slide_preview_url) {
    host.innerHTML = `
      <img class="he-demo-image" src="${patient.slide_preview_url}" alt="H&amp;E preview ${patient.patient_id}" />
      <p class="muted he-caption">Demo H&amp;E thumbnail · ${patient.patient_id}</p>
    `;
    return;
  }

  host.innerHTML = `
    <div class="he-placeholder">
      <div class="he-grid"></div>
      <p>Whole-slide image viewer</p>
      <p class="muted">Drop an .svs / .png or run the demo pipeline to fetch WSIs</p>
    </div>
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
  renderHeSlide(patient);
  refreshEmbedding();
}

function refreshEmbedding() {
  const display = getDisplayPatients();
  buildEmbeddingPlot({
    container: document.getElementById("embedding-plot"),
    patients: display,
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
      const r = p.recurrence_predictions || {};
      const blob = [
        p.patient_id,
        p.histology,
        p.driver_mutation,
        p.archetype,
        p.treatment_category,
        r.preferred_at_recurrence,
        r.targeted_therapy?.label,
        r.immunotherapy?.label,
        r.targeted_therapy?.recommended_agents,
        r.immunotherapy?.recommended_regimen,
        ...(p.treatment?.agents || []),
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
