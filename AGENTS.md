# Agent instructions

## Cursor Cloud specific instructions

- The HistoTME setup requires Python venv support. If `.venv-histotme` is not
  already available, install `python3.12-venv` first because the base image may
  be missing `ensurepip`.
- Prepare the HistoTME environment with:

  ```bash
  bash scripts/setup_histotme.sh
  ```

  This creates `.venv-histotme` for commands such as checkpoint downloads.
