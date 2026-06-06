# Agent instructions

## Active development branch

Slide-deck, pitch, and related Emma research work should be committed to:

`cursor/emma-research-slide-deck-5384`

Before making changes, confirm you are on that branch (`git checkout cursor/emma-research-slide-deck-5384`). Push all commits to `origin/cursor/emma-research-slide-deck-5384`.

## Cursor Cloud specific instructions

- The HistoTME setup requires Python venv support. If `.venv-histotme` is not
  already available, install `python3.12-venv` first because the base image may
  be missing `ensurepip`.
- Prepare the HistoTME environment with:

  ```bash
  bash scripts/setup_histotme.sh
  ```

  This creates `.venv-histotme` for commands such as checkpoint downloads.
