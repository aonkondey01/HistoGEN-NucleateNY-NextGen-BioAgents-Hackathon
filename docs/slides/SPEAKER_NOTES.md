# Speaker notes — PEAT-Nucleate Lung TME deck

Approximate timing: **12–15 minutes** (14 slides).

Stack on `main`: **PHOENIX** (virtual spatial transcriptomics atlas), **GigaTIME**
(virtual mIF from H&E), **Claude Haiku** (patient similarity + vMTB agent in the
SpatialMTB UI).

---

## Slide 1 — Title (~30 sec)

Open with the tension: trials enroll by mutation, but two patients with the same EGFR or KRAS alteration can have completely different outcomes. The missing variable is the tumor microenvironment — how immune and stromal cells are organized in space, not just whether a mutation is present.

---

## Slide 2 — The clinical problem (~1 min)

NSCLC treatment is increasingly precision-driven. Targeted therapies work — until they don't. Immunotherapy combinations that succeeded in wild-type disease often fail in EGFR- or ALK-driven tumors. Trial summaries report medians for "mutation-positive" groups, hiding heterogeneity within those groups. The question for this project: what differs between responders and non-responders who share the same driver?

---

## Slide 3 — Trial examples (~1.5 min)

Walk through the table row by row:

- **KEYNOTE-789 / CheckMate 722:** EGFR-mutant, post-TKI — adding checkpoint inhibitors to chemotherapy did not improve survival. Same mutation, no added benefit.
- **TATTON:** Osimertinib plus durvalumab — stopped due to interstitial lung disease. Biology and toxicity both matter.
- **IMpower151:** Could not reproduce IMpower150 signal in EGFR/ALK-enriched population.
- **CodeBreaK 200:** KRAS G12C inhibitor improved PFS but not OS — resistance and ecosystem effects dominate over time.

Takeaway: genotype-qualified enrollment is not enough.

---

## Slide 4 — Hypothesis (~1 min)

Patients with identical drivers occupy different TME states — immune desert, macrophage-rich, stroma-barrier, etc. Spatial layout matters: effector T cells may be present but excluded from tumor nests. Spatial transcriptomics is the gold standard, but trials rarely have it at scale. We need a scalable first pass on standard H&E.

**Nuance if asked:** EGFR/ALK tumors often have *low* mutational burden and cold immune phenotypes — the problem isn't always "too many mutations."

---

## Slide 5 — PHOENIX + GigaTIME (~1 min)

**PHOENIX** provides a pan-cancer TCGA cell atlas with spatial NEST embeddings —
a reference for virtual spatial transcriptomics at population scale.

**GigaTIME** translates routine H&E into virtual multiplex immunofluorescence
(21 protein channels) for TME phenotyping without extra staining.

Together they let us ask ecosystem questions on archived diagnostic slides.

---

## Slide 6 — TME readouts (~1 min)

Stress interpretability: immune infiltration, macrophage programs, stromal
barriers, angiogenesis, hypoxia — real biology inferred from morphology and
reference atlases. Cluster patients by combined virtual RNA + protein signatures;
compare to trial outcomes within mutation strata.

---

## Slide 7 — Bulk vs spatial (~45 sec)

Spatial maps are the pitch differentiator — one H&E slide becomes layered virtual
RNA and protein views. This is a computational screening analogue of multiplex
imaging and spatial transcriptomics.

---

## Slide 8 — Repo pipeline (~1 min)

This repo wires it together: TCGA lung diagnostic slides, PHOENIX atlas fetch,
GigaTIME inference helpers, light-Zarr slide stores, and the SpatialMTB UI.
Pilot with a few slides for the hackathon; scale to the full cohort later.

---

## Slide 9 — vs ground-truth spatial (~1 min)

Don't position virtual models as replacements. Visium/Xenium / physical mIF =
ground truth, limited scale. PHOENIX + GigaTIME = screening on archived H&E.
Proposed workflow: screen virtually → validate mechanism on a spatial subset.

---

## Slide 10 — Proposed analysis (~1 min)

Stratify by EGFR/ALK/KRAS/wild-type. Cluster TME archetypes. Ask whether non-responders within a mutation stratum share spatial TME patterns. Frame TCGA as retrospective hypothesis generation for trial re-analysis.

---

## Slide 11 — Deliverables (~1 min)

Be honest about what's live vs stretch: pilot slides, virtual RNA/protein maps on exemplars, Haiku-powered similarity clusters, SpatialMTB UI mock-up.

---

## Slide 12 — Team (~30 sec)

Introduce team and roles.

---

## Slide 13 — Ask (~30 sec)

What we need from mentors / judges: feedback on clinical framing, access to
comparator cohorts, or partnership on validation.

---

## Slide 14 — Thank you

Close with the one-liner: *same mutation, different ecosystem, different outcome.*
