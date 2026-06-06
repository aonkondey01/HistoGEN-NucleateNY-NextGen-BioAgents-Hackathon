/** Procedural per-patient spatial tiles (demo until predict_spatial.py output is wired). */

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

function hashSeed(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed) {
  let s = seed;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

function normSig(value) {
  return 1 / (1 + Math.exp(-value));
}

export function generateSpatialTiles(patient, grid = 40) {
  const rand = rng(hashSeed(patient.case_id));
  const sig = patient.signatures || {};
  const tregBase = normSig(sig.Treg ?? 0);
  const effectorBase = normSig(sig.Effector_cells ?? 0);
  const macBase = normSig(sig.Macrophages ?? 0);
  const cafBase = normSig(sig.CAF ?? 0);
  const mdscBase = normSig(sig.MDSC ?? 0);
  const tcellBase = normSig(sig.T_cells ?? 0);
  const checkpointBase = normSig(sig.Checkpoint_inhibition ?? 0);
  const angioBase = normSig(sig.Angiogenesis ?? 0);

  const archetypeShift = {
    "Immune Desert": { te: -0.25, tr: 0.2, mac: -0.1 },
    "Immune Inflamed": { te: 0.3, tr: -0.2, mac: 0.1 },
    "Myeloid/Treg-rich": { te: -0.15, tr: 0.35, mac: 0.25 },
    "Stroma-high": { te: -0.1, tr: 0.05, mac: 0.05 },
  }[patient.archetype] || { te: 0, tr: 0, mac: 0 };

  const tiles = [];
  for (let gy = 0; gy < grid; gy += 1) {
    for (let gx = 0; gx < grid; gx += 1) {
      const cx = gx / grid - 0.5;
      const cy = gy / grid - 0.5;
      const dist = Math.hypot(cx, cy);
      const angle = Math.atan2(cy, cx);
      const nest = Math.max(0, 1 - dist * 2.2);
      const noise = (rand() - 0.5) * 0.12;

      const Treg = Math.min(
        1,
        Math.max(0, tregBase * nest + archetypeShift.tr + noise + (angle > 0 ? 0.08 : 0)),
      );
      const Effector_cells = Math.min(
        1,
        Math.max(0, effectorBase * (1 - nest * 0.5) + archetypeShift.te + noise + dist * 0.35),
      );
      const Macrophages = Math.min(
        1,
        Math.max(0, macBase * (0.4 + Math.abs(cx)) + archetypeShift.mac + noise),
      );
      const CAF = Math.min(1, Math.max(0, cafBase * (0.3 + cy + 0.5) + noise));
      const MDSC = Math.min(1, Math.max(0, mdscBase * nest * 0.9 + noise * 0.5));
      const T_cells = Math.min(1, Math.max(0, tcellBase * (1 - dist) + archetypeShift.te * 0.5 + noise));
      const Checkpoint_inhibition = Math.min(1, Math.max(0, checkpointBase * nest + noise));
      const Angiogenesis = Math.min(1, Math.max(0, angioBase * (0.5 + Math.abs(cy)) + noise));

      tiles.push({
        x: gx * 512,
        y: gy * 512,
        Treg,
        Effector_cells,
        Macrophages,
        CAF,
        MDSC,
        T_cells,
        Checkpoint_inhibition,
        Angiogenesis,
      });
    }
  }

  return { case_id: patient.case_id, tile_size: 256, tiles, signatures: SIGNATURES };
}

export { SIGNATURES };
