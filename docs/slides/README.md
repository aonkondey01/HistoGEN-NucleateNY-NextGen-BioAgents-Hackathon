# Lung cancer TME slide deck

**Branch:** commit all slide-deck and related work to `cursor/emma-research-slide-deck-5384`.

## Files

| File | Description |
|------|-------------|
| `PEAT-Nucleate-Lung-TME-Deck.pptx` | 14-slide PowerPoint deck (speaker notes included) |
| `SPEAKER_NOTES.md` | Plain-text speaker notes for quick editing |

## Regenerate the deck

After editing slide content in `scripts/build_lung_tme_slide_deck.py`:

```bash
pip install python-pptx
python scripts/build_lung_tme_slide_deck.py
```

## Customization tips

- **Team / author names:** edit slide 1 in the build script (`cred` textbox).
- **Trial table:** edit the `rows` list on slide 3.
- **Figures:** HistoTME diagrams are pulled from `external/HistoTME/figures/` (requires submodule init).
- **Export to PDF:** open in PowerPoint or LibreOffice Impress → File → Export as PDF.
