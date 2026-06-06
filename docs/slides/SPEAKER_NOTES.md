# Speaker notes — PEAT-Nucleate Lung TME deck

Approximate timing: **12–15 minutes** (14 slides).

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

## Slide 5 — HistoTME (~1 min)

HistoTME infers 29 curated gene-expression signatures from H&E using foundation-model patch embeddings and multiple-instance learning. No extra staining. Published in NSCLC; HistoTMEv2 extends pan-cancer. Bulk mode = one profile per slide; spatial mode = tile-level maps.

---

## Slide 6 — 29 signatures (~1 min)

Stress interpretability: Treg, MDSC, macrophages, effector T cells, CAF, angiogenesis, EMT — real biology. Downstream clustering yields Immune Desert vs Immune Inflamed, validated against IHC in published work. Immune Inflamed predicted better ICI outcomes than PD-L1 alone in several subgroups.

---

## Slide 7 — Bulk vs spatial (~45 sec)

Point to the figure. Spatial mode is the pitch differentiator — one H&E slide becomes a multi-layer TME map. This is a computational screening analogue of spatial transcriptomics.

---

## Slide 8 — Repo pipeline (~1 min)

This repo wires it together: 1,053 TCGA lung diagnostic slides, download scripts, HistoTME inference, outputs for a dashboard. Pilot with 3 slides for the hackathon; scale to full cohort later.

---

## Slide 9 — vs spatial transcriptomics (~1 min)

Don't position HistoTME as a replacement. Visium/Xenium = ground truth, limited scale. HistoTME = screening on archived H&E. Proposed workflow: screen with HistoTME → validate mechanism on a spatial transcriptomics subset.

---

## Slide 10 — Proposed analysis (~1 min)

Stratify by EGFR/ALK/KRAS/wild-type. Cluster TME archetypes. Ask whether non-responders within a mutation stratum share spatial TME patterns. Frame TCGA as retrospective hypothesis generation for trial re-analysis.

---

## Slide 11 — Deliverables (~1 min)

Be honest about what's live vs stretch: pilot slides, bulk predictions, spatial heatmaps on exemplars, mutation-stratified clusters, UI mock-up.

---

## Slide 12 — Impact (~45 sec)

Close strong: enrich trials by TME, explain failed mutation-positive arms, use existing biobanks. "Mutation is the lock. TME is whether the key turns."

---

## Slide 13 — References (~15 sec)

Available for Q&A.

---

## Slide 14 — Thank you

Invite questions on trials, spatial validation, and demo timeline.

---

## Anticipated Q&A

**"Is this real spatial transcriptomics?"**  
No — it's predicted signature activity from H&E, validated against RNA signatures and IHC. Spatial transcriptomics is the validation layer.

**"Why TCGA if there are no trial arms?"**  
Large lung cohort with H&E + molecular data for hypothesis generation; trial biobanks next.

**"EGFR patients respond great to TKIs — why focus on failure?"**  
Initial response is strong; we're explaining resistance, combination failures, and heterogeneity of durability.
