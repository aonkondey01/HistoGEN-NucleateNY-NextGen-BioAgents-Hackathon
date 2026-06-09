# Representative 20-patient TCGA genomic data package

## Important: exome vs whole genome

TCGA lung open somatic mutation files are **WXS (whole-exome)** MAFs, not true
whole-genome (WGS) mutation calls. Mutation maps in this folder therefore reflect
**exome-covered regions**, not the entire 3 Gb genome.

Available open-access genomic modalities for these 20 patients:

| Modality | Files | Notes |
|----------|------:|-------|
| Masked somatic MAF (WXS) | 22 | Raw `.maf.gz` in `raw_files/maf/` |
| Copy-number segments | 151 | SNP6 array + limited WGS segments |
| Gene-level copy number | 61 | Parsed to `parsed_tables/` |
| DNA methylation beta | 26 | Raw files in `raw_files/methylation/` |
| miRNA expression | 18 | Parsed to `parsed_tables/mirna_expression.csv` |

## Regenerate

```bash
python3 data/tcga_lung/download_representative_genomic_data.py --workers 8
```

Use `--skip-methylation` to omit ~300 MB methylation downloads.

## Mutation maps

- `mutation_maps/genome_mutation_landscape.csv` — every MAF variant with chromosome coordinates
- `mutation_maps/mutations_by_chromosome.csv` — per-patient chromosome counts
- `mutation_maps/mutations_by_1mb_bin.csv` — 1 Mb genome bins (exome-covered loci)
- `mutation_maps/top_mutated_genes_by_patient.csv`
- `mutation_maps/variant_classification_summary.csv`

## Manifests

GDC download manifests for gdc-client or `download.py`:

- `gdc_manifest.all_genomic.txt`
- `gdc_manifest.maf.txt`
- `gdc_manifest.copy_number_segment.txt`
- etc.
