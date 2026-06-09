# Representative 20-patient TCGA lung data package

Complete TCGA clinical and molecular data for the 20 representative patients selected in `../representative_20_patients.csv`.

## Regenerate everything

```bash
python3 data/tcga_lung/extract_representative_patient_data.py --workers 8
```

This downloads from GDC:

- full clinical metadata (flat CSV + nested JSON)
- genome-wide RNA-seq STAR gene counts (~60,660 genes per sample)
- full RPPA proteomics (~487 peptide targets where available)
- full masked somatic MAF mutation calls
- diagnostic H&E slide metadata and molecular file indexes

## Package layout

| Path | Description |
|------|-------------|
| `clinical/clinical_metadata.csv` | 20 rows, all extracted clinical fields |
| `clinical/clinical_metadata.json` | Nested GDC clinical records |
| `somatic_mutations.csv` | All MAF SNV/indel rows for the 20 patients |
| `genome_wide_gene_expression.csv` | All STAR gene-count rows (~1.33M rows; generated locally) |
| `rppa_protein_expression.csv` | All RPPA peptide-target measurements |
| `important_gene_*.csv` | Focused 30-gene mutation/RNA/RPPA subset |
| `molecular_file_index.csv` | GDC file IDs/URLs for mutation + RNA files |
| `slide_metadata.json` | Diagnostic slide file metadata for WSI download |
| `data_availability_summary.csv` | Per-patient row counts and file availability |
| `per_patient/<TCGA-ID>/` | One bundle per patient with the same tables split out |

## Notes

- **RPPA coverage:** 14/20 patients have RPPA proteomics in TCGA; 6 have RNA + mutations only.
- **Multiple files:** Some patients have more than one RNA or MAF file (multiple tumor samples).
- **WSI slides:** Slide metadata is included; raw `.svs` images are not downloaded here. Use `data/tcga_lung/download.py` with the slide manifest if needed.
- **Fusions/CNV:** MAF files capture SNVs/indels only; ALK/ROS1/RET fusions and copy-number events require separate assays.
