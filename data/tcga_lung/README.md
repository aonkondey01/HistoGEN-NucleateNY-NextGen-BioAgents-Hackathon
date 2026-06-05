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

| File                                      | Description                                                       |
| ----------------------------------------- | ----------------------------------------------------------------- |
| `generate_manifest.py`                    | Queries the GDC API and (re)writes all manifests + metadata below |
| `fetch_clinical_metadata.py`              | Queries the GDC cases API for LUAD/LUSC clinical metadata         |
| `download.py`                             | Downloads slides from a manifest (gdc-client or built-in HTTP)    |
| `gdc_manifest.tcga_lung.txt`              | Combined gdc-client manifest (all 1,053 slides)                   |
| `gdc_manifest.TCGA-LUAD.txt`              | Per-project manifest (541 slides)                                 |
| `gdc_manifest.TCGA-LUSC.txt`              | Per-project manifest (512 slides)                                 |
| `slides_metadata.tcga_lung.json`          | Rich per-slide metadata (file id, md5, size, patient/case ids)    |
| `clinical_metadata.tcga_lung.json`        | Full expanded GDC clinical case records for LUAD/LUSC             |
| `clinical_patient_summary.tcga_lung.tsv`  | One-row-per-patient clinical summary for joins                    |
| `clinical_summary.tcga_lung.json`         | Clinical cohort counts for quick inspection                       |
| `summary.json`                            | Slide counts + total size for quick reference                     |

The manifests and metadata are committed so you don't need network access just
to inspect the cohort. Regenerate them any time with `generate_manifest.py`
(the GDC dataset is occasionally updated).

## Quick start

### 1. (Optional) Refresh the manifest from GDC

```bash
python generate_manifest.py
```

### 1b. (Optional) Refresh clinical metadata from GDC

```bash
python fetch_clinical_metadata.py
```

This writes the complete expanded GDC case records for all TCGA-LUAD/LUSC
patients plus a flattened patient-level TSV. The raw JSON preserves nested
demographic, diagnosis, treatment, exposure, follow-up, sample, and project
metadata; the TSV adds `has_diagnostic_slide` and `n_diagnostic_slides` for
joining back to the diagnostic-slide manifest.

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
