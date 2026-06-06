import Plotly from "plotly.js-dist-min";

const BENEFIT_COLORS = {
  "Likely benefit": "#0d9488",
  "Uncertain benefit": "#d97706",
  "Unlikely benefit": "#dc2626",
};

const PREFERRED_COLORS = {
  "Targeted therapy first": "#4e79a7",
  "Immunotherapy first": "#e15759",
  "Consider combination or trial": "#9ca3af",
};

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
  if (key.endsWith("_benefit")) return BENEFIT_COLORS[value] || "#94a3b8";
  if (key === "preferred_at_recurrence") return PREFERRED_COLORS[value] || "#94a3b8";
  if (key === "archetype") return ARCHETYPE_COLORS[value] || "#94a3b8";
  if (key === "driver_mutation") return DRIVER_COLORS[value?.split(";")[0]] || "#94a3b8";
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
  const r = patient.recurrence_predictions || {};
  switch (colorBy) {
    case "targeted_benefit":
      return r.targeted_therapy?.label;
    case "immunotherapy_benefit":
      return r.immunotherapy?.label;
    case "preferred_at_recurrence":
      return r.preferred_at_recurrence;
    case "archetype":
      return patient.archetype;
    case "treatment_category":
      return patient.treatment?.category || patient.treatment_category;
    case "disease_response":
      return patient.clinical?.disease_response || patient.disease_response;
    case "stage":
      return patient.stage || patient.clinical?.stage;
    case "driver_mutation":
      return patient.driver_mutation || patient.driver;
    default:
      return r.targeted_therapy?.label;
  }
}

export function buildEmbeddingPlot({ container, patients, colorBy, selectedId, onSelect }) {
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
      const r = p.recurrence_predictions || {};
      const tgt = r.targeted_therapy || {};
      const io = r.immunotherapy || {};
      return [
        p.patient_id,
        p.archetype,
        p.driver_mutation || p.driver,
        `Targeted @ recurrence: ${tgt.label || "—"} (${tgt.score ?? "—"})`,
        `IO @ recurrence: ${io.label || "—"} (${io.score ?? "—"})`,
        r.preferred_at_recurrence || "",
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
