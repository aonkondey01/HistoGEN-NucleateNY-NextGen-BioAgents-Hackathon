# Lung TCGA H&E (FFPE Diagnostic) Whole-Slide Images

This directory contains everything needed to download **all** lung TCGA
hematoxylin & eosin (H&E) diagnostic whole-slide images (WSIs) — the
computation-grade slides used to train and evaluate pathology foundation models.

## What "lung TCGA H&E" means here

TCGA's lung cohort is split across two projects, both included:

| Project     | Cancer type                  | Diagnostic slides |
| ----------- | ---------------------------- | ----------------- |
| `TCGA-LUAD` | Lung adenocarcinoma          | 541               |
| `TCGA-LUSC` | Lung squamous cell carcinoma | 512               |
| **Total**   |                              | **1,053**         |

- **956 unique patients**
- **~824 GB** total (`.svs` format, avg ~782 MB/slide)
- **Open access** — no dbGaP / controlled-access token required

> **Diagnostic vs. frozen slides.** TCGA ships both frozen-tissue (`-TS`/`-BS`)
> and FFPE **diagnostic** (`-DX`) slides. Only the FFPE diagnostic slides are
> H&E-stained and clean enough for computational pathology, so we filter on
> `experimental_strategy == "Diagnostic Slide"`. Every file here has a `DX` in
> its name.

## How the data is sourced

All data comes from the NCI **Genomic Data Commons (GDC)** REST API
(`https://api.gdc.cancer.gov`). The filter used is:

```json
{
  "op": "and",
  "content": [
    { "op": "in", "content": { "field": "cases.project.project_id", "value": ["TCGA-LUAD", "TCGA-LUSC"] } },
    { "op": "in", "content": { "field": "files.data_type", "value": ["Slide Image"] } },
    { "op": "in", "content": { "field": "files.experimental_strategy", "value": ["Diagnostic Slide"] } }
  ]
}
```

This is the programmatic equivalent of the manual GDC Data Portal workflow
(Repository → Data Type: *Slide Image* → Experimental Strategy: *Diagnostic
Slide* → Project: *TCGA-LUAD/LUSC* → add to cart → download manifest).

## Files in this directory

| File                                | Description                                                       |
| ----------------------------------- | ----------------------------------------------------------------- |
| `generate_manifest.py`              | Queries the GDC API and (re)writes all manifests + metadata below |
| `extract_patient_metadata.py`       | Extracts patient clinical metadata plus mutation/expression file indexes |
| `extract_important_lung_genes.py`   | Streams public GDC files and extracts important LUAD/LUSC gene data |
| `visualize_important_lung_genes.py` | Builds an HTML/SVG visual summary report from the extracted tables |
| `generate_visualization_powerpoint.py` | Builds a PowerPoint deck from the SVG plots in `visual_report/plots/` |
| `download.py`                       | Downloads slides from a manifest (gdc-client or built-in HTTP)    |
| `gdc_manifest.tcga_lung.txt`        | Combined gdc-client manifest (all 1,053 slides)                   |
| `gdc_manifest.TCGA-LUAD.txt`        | Per-project manifest (541 slides)                                 |
| `gdc_manifest.TCGA-LUSC.txt`        | Per-project manifest (512 slides)                                 |
| `slides_metadata.tcga_lung.json`    | Rich per-slide metadata (file id, md5, size, patient/case ids)    |
| `patient_metadata.tcga_lung.csv`    | One row per slide-cohort patient with clinical fields from GDC     |
| `patient_metadata.tcga_lung.json`   | Same patient rows plus raw diagnoses/exposures/treatments/follow-ups |
| `molecular_files.tcga_lung.csv`     | Open mutation/expression GDC file index for these patients         |
| `molecular_files.tcga_lung.json`    | JSON version of the molecular file index                           |
| `gdc_manifest.mutation.tcga_lung.txt` | gdc-client manifest for masked somatic mutation MAF files        |
| `gdc_manifest.expression.tcga_lung.txt` | gdc-client manifest for RNA-seq STAR-count expression files    |
| `patient_metadata_summary.tcga_lung.json` | Counts and missingness for the extracted patient metadata     |
| `important_lung_genes/`             | Focused mutation, RNA expression, and RPPA protein expression tables for important LUAD/LUSC genes |
| `important_lung_genes/visual_report/index.html` | Browser-viewable cohort, mutation, clinical, and survival summary |
| `important_lung_genes/visual_report/gallery.html` | Standalone plot gallery for all SVG charts |
| `important_lung_genes/visual_report/plots/` | Individual SVG plots for cohort, demographics, mutations, and survival |
| `summary.json`                      | Counts + total size for quick reference                           |

The manifests and metadata are committed so you don't need network access just
to inspect the cohort. Regenerate them any time with `generate_manifest.py`
(the GDC dataset is occasionally updated).

## Patient, clinical, mutation, and expression metadata

The slide metadata identifies 956 unique TCGA lung patients/cases. To extract
clinical and molecular metadata for exactly those patients, run:

```bash
python extract_patient_metadata.py
```

This writes `patient_metadata.tcga_lung.csv` with columns for:

- age at diagnosis, sex, race, ethnicity,
- smoking/exposure history,
- survival and vital status,
- diagnosis timing,
- AJCC/pathologic staging,
- treatment summaries,
- counts of available mutation and expression files.

The companion JSON keeps the raw GDC `diagnoses`, `exposures`, `treatments`,
and `follow_ups` arrays for each patient so no repeated clinical records are
lost during CSV flattening.

Mutation and expression payloads themselves are large and are not committed.
Instead, `molecular_files.tcga_lung.csv` indexes the open GDC files and the
two `gdc_manifest.*.tcga_lung.txt` files can be used with `gdc-client`:

```bash
gdc-client download -m gdc_manifest.mutation.tcga_lung.txt -d ./molecular_data/mutation -n 8
gdc-client download -m gdc_manifest.expression.tcga_lung.txt -d ./molecular_data/expression -n 8
```

## Important LUAD/LUSC genes

To extract a compact public TCGA dataset for important lung adenocarcinoma and
lung squamous cell carcinoma genes, run:

```bash
python extract_important_lung_genes.py
```

The extractor streams public GDC files and writes focused outputs under
`important_lung_genes/`:

- `important_lung_cancer_genes.csv` — the selected important genes and why they
  were included.
- `important_mutations.tcga_lung.csv` — MAF mutation rows for those genes.
- `important_gene_expression.tcga_lung.csv` — RNA-seq STAR count/TPM/FPKM rows
  for those genes.
- `important_protein_expression.tcga_lung.csv` — RPPA protein-expression rows
  where the TCGA antibody target maps to one of those genes.
- `important_lung_gene_summary.tcga_lung.json` — counts by gene/project and
  extraction notes.

Important limitation: MAF files capture small variants such as SNVs/indels.
Targetable fusions (`ALK`, `ROS1`, `RET`, `NTRK`) and copy-number events
(`SOX2`, `FGFR1`, `TP63`, etc.) require additional fusion/CNV data types and
are not fully represented by the mutation MAF output.

## Visual summary report

To build the dependency-free HTML/SVG report:

```bash
python visualize_important_lung_genes.py
```

Open the generated report in Cursor or a browser:

```text
important_lung_genes/visual_report/index.html
important_lung_genes/visual_report/gallery.html
important_lung_genes/visual_report/plots/
```

The report and plot gallery summarize:

- number of patients/samples and slide counts,
- clinical demographics such as age, sex, race/ethnicity, smoking, stage, and
  vital status,
- important-gene mutation frequencies by LUAD/LUSC,
- clinical summaries by mutation status,
- exploratory Kaplan-Meier/log-rank survival comparisons for mutation status,
  RNA expression median splits, and RPPA protein-expression median splits.

Direct drug-resistance labels are not uniformly available in the extracted GDC
clinical fields, so the report uses survival, progression/recurrence, disease
response, and treatment outcome fields as exploratory clinical endpoints.

Build a PowerPoint deck containing all visualizations:

```bash
pip install python-pptx pillow cairosvg
python generate_visualization_powerpoint.py
```

Output:

```text
important_lung_genes/visual_report/TCGA_Lung_Visual_Summary.pptx
```

## Quick start

### 1. (Optional) Refresh the manifest from GDC

```bash
python generate_manifest.py
```

### 2. Preview / pilot before committing ~824 GB

```bash
# See what would be downloaded (no files written)
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run

# Grab a small pilot first (3 slides)
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --limit 3
```

### 3. Full download

```bash
python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --workers 8
```

`download.py` automatically uses the official **`gdc-client`** if it's on your
`PATH`, otherwise it falls back to a built-in parallel HTTP downloader. Both
backends:

- lay files out as `WSI/<file_id>/<file_name>.svs` (identical layout),
- **resume** partially downloaded slides, and
- **verify md5** checksums against the manifest (HTTP backend; `gdc-client`
  verifies natively).

Re-running the command is safe and idempotent — completed slides are skipped.

### Using the official gdc-client directly

If you prefer the official tool (recommended for very large pulls), install it
from <https://gdc.cancer.gov/access-data/gdc-data-transfer-tool> and run:

```bash
gdc-client download -m gdc_manifest.tcga_lung.txt -d ./WSI -n 8
```

## Storage planning

| Subset      | Slides | Approx. size |
| ----------- | ------ | ------------ |
| TCGA-LUAD   | 541    | ~430 GB      |
| TCGA-LUSC   | 512    | ~395 GB      |
| **Full**    | 1,053  | **~824 GB**  |

Make sure the target volume has headroom (slides are stored uncompressed-ish
pyramidal TIFFs). The `WSI/` output directory is git-ignored.

## Reading the slides

`.svs` is a pyramidal TIFF (Aperio). Read it with
[OpenSlide](https://openslide.org/) (`openslide-python`) or `tiffslide` for
tiling/feature extraction in the foundation-model pipeline.
