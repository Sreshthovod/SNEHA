# UI QA tools (synthetic data only)

- `seed_synthetic.py`: seeds a running **dev** API with one fictional family through the
  public API (and verifies the synthetic clinician with `scripts/manage.py`). Never point it
  at a real deployment.
- `screenshots.mjs`: headless Chrome over the DevTools protocol. It signs in, sets viewport
  and colour scheme, optionally stores a `localStorage` value (`--local`) and clicks a button
  or `<summary>` (`#click=`), then captures full-page PNGs and a `report.json` with
  horizontal overflow per capture.
- Patient app: `apps/patient_app/test/ui_qa/screenshots_test.dart`.

See [docs/ui-ux-validation.md](../../docs/ui-ux-validation.md) for commands and results.
