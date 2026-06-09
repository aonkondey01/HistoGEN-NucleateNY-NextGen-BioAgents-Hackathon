# Agent skill: Cohort visual report (memorized figures)

## Source

Path: `demo/visual_report/selected figures/`
PowerPoint: `Representative_20_Patients_Summary.pptx`

Seven figures are exported as PNG + SVG and loaded into the advisor knowledge base at demo time.

## Trigger phrases

- "show driver mutation frequency"
- "show vital status"
- "show treatment types"
- "show cohort age distribution"
- "show pathologic stage"
- "show variant classification"
- "show sex distribution"
- "what cohort figures do you know"

## Demo figures

| Title | Try in chat |
|-------|-------------|
| Age at diagnosis distribution | `show cohort age distribution` |
| Vital status | `show vital status` |
| Sex distribution | `show sex distribution` |
| AJCC pathologic stage | `show pathologic stage` |
| Top driver-gene mutation frequency | `show driver mutation frequency` |
| Variant classification (cohort-wide) | `show variant classification` |
| Treatment types (patient mentions) | `show treatment types` |

## Behavior

1. Match the user message against figure keywords / titles.
2. Call `GET /api/agent/cohort-figures/match?q=...` on the local UI server.
3. Render an agent reply with the memorized PNG, title, and summary text.

List all memorized figures: `GET /api/agent/cohort-figures`
