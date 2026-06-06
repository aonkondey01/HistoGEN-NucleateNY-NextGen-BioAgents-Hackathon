import Plotly from "plotly.js-dist-min";

const BENEFIT_COLORS = {
  "Likely benefit": "#0d9488",
  "Uncertain benefit": "#d97706",
  "Unlikely benefit": "#dc2626",
};

const TREATMENT_COLORS = {
  "Pharmaceutical": "#4e79a7",
  "Chemotherapy": "#59a14f",
  "Pharma + Radiation": "#b07aa1",
  "Chemo + Radiation": "#edc948",
  Radiation: "#f28e2b",
  Surgery: "#76b7b2",
  "None documented": "#9ca3af",
};

const DRIVER_COLORS = {
  EGFR: "#b07aa1",
  "KRAS G12C": "#59a14f",
  ALK: "#edc948",
  WT: "#9c755f",
};

const OS_COLORS = { alive: "#008080", deceased: "#6b7280" };

const PALETTE = [
  "#4e79a7",
  "#f28e2b",
  "#e15759",
  "#76b7b2",
  "#59a14f",
  "#edc948",
  "#b07aa1",
  "#ff9da7",
  "#9c755f",
  "#bab0ac",
];

function colorForValue(key, value) {
  if (value == null || value === "") return "#cbd5e1";
  if (key === "predicted_benefit") return BENEFIT_COLORS[value] || "#94a3b8";
  if (key === "treatment_category") return TREATMENT_COLORS[value] || "#94a3b8";
  if (key === "driver_mutation") return DRIVER_COLORS[value?.split(";")[0]] || "#94a3b8";
  if (key === "vital_status") {
    const v = String(value).toLowerCase();
    if (v === "alive") return OS_COLORS.alive;
    if (v === "dead") return OS_COLORS.deceased;
    return "#94a3b8";
  }
  return null;
}

function categoricalColors(patients, key, getter) {
  const values = [...new Set(patients.map(getter))].filter(Boolean);
  const map = {};
  values.forEach((v, i) => {
    map[v] = colorForValue(key, v) || PALETTE[i % PALETTE.length];
  });
  return patients.map((p) => map[getter(p)] || "#94a3b8");
}

function getColorValue(patient, colorBy) {
  switch (colorBy) {
    case "predicted_benefit":
      return patient.predicted_benefit?.label;
    case "treatment_category":
      return patient.treatment?.category || patient.treatment_category;
    case "disease_response":
      return patient.clinical?.disease_response || patient.disease_response;
    case "vital_status":
      return patient.clinical?.vital_status;
    case "stage":
      return patient.stage || patient.clinical?.stage;
    case "histology":
      return patient.histology;
    case "driver_mutation":
      return patient.driver_mutation || patient.driver;
    case "smoking":
      return patient.smoking;
    default:
      return patient.archetype;
  }
}

export function buildEmbeddingPlot({
  container,
  patients,
  colorBy,
  selectedId,
  onSelect,
}) {
  if (!container || !patients.length) {
    if (container) container.innerHTML = `<p class="muted" style="padding:1rem">No patients match filter.</p>`;
    return;
  }

  const colors = categoricalColors(patients, colorBy, (p) => getColorValue(p, colorBy));
  const sizes = patients.map((p) => (p.patient_id === selectedId ? 14 : 7));
  const opacity = patients.map((p) => (p.patient_id === selectedId ? 1 : 0.65));

  const trace = {
    x: patients.map((p) => p.umap_x),
    y: patients.map((p) => p.umap_y),
    text: patients.map((p) => {
      const b = p.predicted_benefit;
      return [
        p.patient_id,
        p.archetype,
        p.driver_mutation || p.driver,
        p.treatment?.category || "—",
        b ? `${b.label} (${b.score})` : "",
      ].join("<br>");
    }),
    customdata: patients.map((p) => p.patient_id),
    mode: "markers",
    type: "scattergl",
    marker: {
      color: colors,
      size: sizes,
      line: {
        color: patients.map((p) => (p.patient_id === selectedId ? "#003366" : "rgba(17,24,39,0.35)")),
        width: patients.map((p) => (p.patient_id === selectedId ? 2 : 0.5)),
      },
      opacity,
    },
    hovertemplate: "%{text}<extra></extra>",
  };

  const selected = patients.find((p) => p.patient_id === selectedId);
  const traces = [trace];
  if (selected) {
    traces.push({
      x: [selected.umap_x],
      y: [selected.umap_y],
      mode: "markers",
      type: "scattergl",
      marker: {
        size: 22,
        color: "rgba(0,0,0,0)",
        line: { color: "#003366", width: 3 },
      },
      hoverinfo: "skip",
      showlegend: false,
    });
  }

  const layout = {
    margin: { l: 44, r: 12, t: 12, b: 40 },
    paper_bgcolor: "white",
    plot_bgcolor: "#fafbfc",
    xaxis: { title: "UMAP 1", zeroline: false, gridcolor: "#eceff4" },
    yaxis: { title: "UMAP 2", zeroline: false, gridcolor: "#eceff4" },
    showlegend: false,
    dragmode: "zoom",
  };

  Plotly.react(container, traces, layout, { responsive: true, displayModeBar: false });

  container.on("plotly_click", (ev) => {
    const id = ev.points?.[0]?.customdata;
    if (id && onSelect) onSelect(id);
  });
}
