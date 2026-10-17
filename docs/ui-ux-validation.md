# UI/UX validation

Date: 2026-10-18. This records what was actually checked after the UI/UX redesign and the
memory-personalization work, and how to repeat it. Only synthetic data was used.
Findings referenced by ID come from [ui-ux-audit.md](ui-ux-audit.md); the design rules are in
[design-system-spec.md](design-system-spec.md).

## Tools actually used

| Need | Tool | Notes |
|---|---|---|
| Browser automation and screenshots | `tools/ui-qa/screenshots.mjs`: headless Google Chrome driven over the DevTools protocol (Node 26 built-ins, no dependencies) | No browser, emulator or Figma MCP server was connected in this environment, so this local driver stands in for one. It signs in the way the app does, emulates light or dark and any viewport, clicks a button or `<summary>`, measures horizontal overflow and captures full pages |
| Patient-app screenshots | `apps/patient_app/test/ui_qa/screenshots_test.dart`: real screens rendered in `flutter test` with Roboto and Material Icons loaded from the Flutter SDK | Skipped unless `--dart-define=SNEHA_SCREENSHOTS=<dir>`. No Android emulator is available here (low disk), and the phone was not connected |
| Realistic data | `tools/ui-qa/seed_synthetic.py`, which uses only the public API on a dev server | One fictional family, "Synthetic …" names, gradient images as stand-in photos |
| Contrast | `python3` WCAG ratio script (Agent B) | About 205 pairs measured; table in the design spec §2.4 |

How the work was split: Agent A wrote the UX and accessibility audit and Agent B the design
system, both read-only and in parallel. Agent C (Flutter) and Agent D (React) then implemented
in parallel with no file overlap. The lead reviewed the work, did the cross-platform QA and
fixes, and wrote this record.

## Reproduce

```bash
# API and dashboard running (scripts/dev_api.sh; npm run dev in apps/web_dashboard)
python3 -I tools/ui-qa/seed_synthetic.py http://127.0.0.1:8000   # prints the synthetic logins
node tools/ui-qa/screenshots.mjs --out /tmp/shots --login <caregiver> --password <pw> \
  --api http://localhost:8000 --web http://localhost:5173 \
  --sizes 1440x900,1280x800,768x1024,390x844 --routes "/app/dashboard,/app/patients/<id>/analytics"
cd apps/patient_app && flutter test test/ui_qa/screenshots_test.dart \
  --dart-define=SNEHA_SCREENSHOTS=/tmp/app-shots
```

Use `localhost`, not `127.0.0.1`. The API's CORS setting allows `http://localhost:5173`, so the
other origin shows "server cannot be reached". This was found during QA, and it is
configuration, not an app bug.

## Results

### Dashboard (React)

| Check | Result | Evidence |
|---|---|---|
| 13 routes × 4 viewports (1440×900, 1280×800, 768×1024, 390×844), caregiver | **0 px horizontal overflow** on all 52 captures | `report.json` from the sweep |
| Clinician dashboard, analytics and history at 1440 and 390 | 0 px overflow; no unconfirmed review prompts; memory titles never shown | sweep, plus `memory-personalization.test.tsx` |
| Login at 1440 and 390 | renders | screenshot |
| Dark mode (dashboard, analytics, people, settings) | readable; shadows replaced by borders | `after_web_dark` (Agent D) |
| **High contrast with OS dark mode (A11Y-01, critical before)** | **Fixed and seen**: a complete light high-contrast palette, no black-on-dark cards | `docs/ui-screenshots/after/hc_dark_dashboard@1440x900.png` |
| Sidebar from 1024 px; drawer below | the drawer traps focus, closes on Escape and the backdrop, sets `aria-expanded`, and returns focus to Menu | Agent D drawer captures + code review |
| Patient sections (NAV-01: 10 tabs overflowed) | grouped into Person, Activity, and Care & privacy; side list from 1360 px, a section menu below | screenshots at all widths |
| Analytics length (DIC-02) | 5,221 → 3,262 px at 1440; 9,471 → 4,767 px at 390 | page heights from `report.json` |
| Duplicate review prompts (DIC-01) | one card per rule; overlapping periods collapsed under "Also raised for …". The backend cause is documented, not changed | screenshot + new test |
| Memory Bank "How SNEHA uses this" | phone status, the activities a memory feeds, linked memories; a summary-row spacing defect was found in QA and fixed | `memory_bank_how_used@1440x900.png`, 390 capture |

### Patient app (Flutter)

| Check | Result | Evidence |
|---|---|---|
| 50 screens, states and display variants (normal, high contrast, dark, 1.5× text) at 360×640 and 412×915 | render with real text; no clipping or overlap found in the screens inspected | 100 captures |
| Button labels | were drawn as boxes in baseline renders (no explicit font family); now real text, because the theme sets `fontFamily: 'Roboto'` with Noto fallbacks | before/after `04_runner` |
| Home on a small phone (COG-02) | greeting, suggestion and the three choices are above the fold at 360×640 | `after/02_home_small_360x640.png` |
| Runner (COG-01, A11Y-02) | two tiers: Hint and I'm tired (64 dp), then Pause, Skip, Stop (≥ 56 dp). Answers scroll and are never covered; about 2 of 3 answers are visible above the fold at 360×640 | `after/04_runner_small_360x640.png` |
| High contrast, dark, 1.5× text | home, activity list, runner, pause, stop dialog, result and story time checked | `v*_highContrast/dark/text150` captures |
| Picture pairs with family photos (new) | the photo filled only a strip of the card; fixed in QA so it fills the card | `after/20_pairs_two_turned_small_360x640.png` |
| Story time guided prompt (new) | prompt built from approved fields, position "Memory 1 of 3", Previous/Next | `after/09_story_time_typical_412x915.png` |

## Tests and builds run (final)

| Suite | Result |
|---|---|
| Dashboard: `tsc -b`, `npm run lint`, `vitest`, `npm run build`, `npm run check:api` | all pass; **67 passed**, 2 skipped |
| Patient app: `flutter analyze`, `flutter test` | no issues; **210 passed**, 8 skipped (the screenshot harness, which only runs on request) |
| API: `ruff`, contract check, `pytest` | all pass; **347 passed**, 3 skipped |

`npm ci` was not re-run because the disk was nearly full.

## Not verified

- Any real Android device or emulator (phone not connected, no AVD).
- Assamese and Bengali glyphs in the Flutter renders: this Mac has no Bengali font for the
  test renderer. The theme declares Noto fallbacks, which Android provides.
- Screen-reader walkthroughs (TalkBack, NVDA, VoiceOver). Semantics were reviewed in code and
  tests only.
- Usability with older adults or caregivers.
