# Representative 20-patient visual summary

Browser-viewable summary of all extracted data for the stratified 20-patient TCGA lung cohort.

## Regenerate

```bash
python3 data/tcga_lung/visualize_representative_patients.py
python3 data/tcga_lung/generate_representative_patient_powerpoint.py
```

## PowerPoint deck

`Representative_20_Patients_Summary.pptx` — native pie charts, bar/column charts with statistics, plus embedded plot images for heatmaps and complex visualizations (39 slides).

## View locally

Open `index.html` in a browser, or browse `gallery.html` for standalone SVG plots.

## Outputs

| File | Description |
|------|-------------|
| `index.html` | Full narrative report with embedded charts |
| `gallery.html` | Plot gallery |
| `master_patient_summary.csv` | One row per patient with clinical + molecular metrics |
| `driver_gene_mutation_matrix.csv` | Patient × driver gene mutation counts |
| `driver_mutation_frequency.csv` | Cohort-level driver mutation frequencies |
| `per_patient_molecular_summary.csv` | Somatic mutation burden per patient |
| `per_patient_cnv_summary.csv` | CNV segment and alteration counts |
| `per_patient_mirna_summary.csv` | miRNA feature counts |
| `cohort_visual_summary.json` | Report-level counts and metadata |
| `plots/` | 10 standalone SVG charts |

## Charts included

1. Cohort composition (LUAD/LUSC × smoker/non-smoker)
2. Clinical demographics (age, sex, stage, vital status)
3. Data availability heatmap (clinical, MAF, RNA, RPPA, CNV, miRNA, methylation, slides)
4. Mutation burden and variant classifications
5. Driver-gene mutation matrix and frequencies
6. Chromosome-level mutation landscape
7. Important-gene RNA expression heatmap
8. CNV amplification/deletion burden
9. miRNA coverage
10. Treatment history and resistance proxies
