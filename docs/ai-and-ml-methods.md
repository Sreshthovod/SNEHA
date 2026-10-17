# AI and ML methods: what SNEHA actually uses

Date: 2026-10-18. This document is the honest inventory asked for by the alignment audit
([original-problem-alignment-audit.md](original-problem-alignment-audit.md)). Provider
setup details (Gemini options, model downloads, reason codes) are in
[ai-models.md](ai-models.md).

**Summary.** SNEHA has **no model trained on project data** and no model that scores,
classifies or predicts a person's cognition. Safety, adaptation, trends and reports are
deterministic rules whose thresholds are in versioned TOML files. Pretrained models are used
only for language understanding (optional, behind a guard) and speech (optional, server-side).
A capability that is not installed or not verified is reported as unavailable. It is never
simulated.

## Inventory

| # | Feature | Technique | Kind | Runs where | Offline |
|---|---|---|---|---|---|
| 1 | In-activity comfort policy (hint, shorten, rest, end) | Priority rules over counted signals (`lib/adaptation/session_policy.dart`, `[in_session]` in `personalization.toml`) | **Rules** | Phone | ✅ |
| 2 | Next activity, difficulty, break, support | Integer scoring, replayed difficulty rules and support rules (`personalization/engine.py`, ALGORITHM 1.2.0, plus a parity-tested Dart port) | **Rules** | Server and phone | ✅ (phone port) |
| 3 | Memory retrieval for activities and conversation | Tag, entity and relationship matching over approved memories | **Rules** | Server; phone uses its approved cache | ✅ |
| 4 | Trends and review prompts | Descriptive statistics against the person's own baseline (`analytics/compute.py`, `analytics.toml`) | **Rules / descriptive statistics** | Server | ❌ (dashboard is online) |
| 5 | Report | ReportLab layout of #4 plus stored records and caregiver decisions | **No model** | Server | n/a |
| 6 | Conversation understanding | Default: keyword rules. Optional: Gemini (`gemini-3.6-flash`, JSON schema output) or a local OpenAI-compatible LLM | **Rules by default; pretrained LLM optional, API-based** | Server; phone has its own keyword helper | Rules ✅; LLM ❌ |
| 7 | Speech recognition | faster-whisper (pretrained Whisper) | **Pretrained, locally executed on the server** | Server only | ❌ |
| 8 | Speech synthesis | Android system TTS on the phone; AI4Bharat Indic Parler-TTS on the server (optional) | **Pretrained (platform / server)** | Phone; server | Phone ✅ if the device has a voice for the language |

## Details per feature

### 1. In-activity comfort policy (new in this pass)

- **Inputs:** stop request; tiredness level and who reported it; wrong answers in the
  current round; hints already shown; struggled rounds (≥ 2 wrong answers, or skipped), in a
  row and in total; rounds left; whether the engine advised hints; whether a rest was already
  offered.
- **Output:** `continue | show_hint | shorten | offer_break | end_session`, plus reason codes
  such as `REPEATED_ERRORS_IN_ROUND`, `MILD_FATIGUE_SHORTEN`, `SEVERE_FATIGUE_END_SESSION`
  and `STOP_REQUESTED`. Every non-trivial decision is stored as an `adaptation` event.
- **Priority:** stop > very tired > a little tired > repeated struggle > repeated wrong
  answers > continue. The policy can only make an activity easier, shorter or end it. A test
  enumerates the inputs and checks it never lengthens a run.
- **Response time is recorded but not used to act.** Per-answer latency is stored with each
  `attempt` event, excluding pauses. Within one activity, slow answers have too many
  everyday causes (reading, hearing, a helper explaining) to justify an action, so the
  policy ignores them.
- **Validation:** `test/adaptation/session_policy_test.dart` (unit) and
  `runner_adaptation_test.dart` (real runner, SQLite and outbox).
- **Evaluation:** none with users yet. Thresholds are design defaults, not tuned values.

### 2. Next-activity engine

As specified in [personalization-rules.md](../packages/shared_docs/personalization-rules.md).
What changed in 1.1.0: a caregiver's fatigue observation can carry a level, and **"very
tired" within 8 h means a break** (`CAREGIVER_REPORTED_SEVERE_FATIGUE`). Caregiver reports
now reach the phone's engine through sync (level and time only), so this also works
offline. Parity: 34 Python-generated scenarios are replayed in Dart.

**1.2.0 (adaptive support):** three more rules, each needing a pattern over several results:
hint support after hint-heavy runs, a gentler activity after struggling at an activity's easiest
level, and reading questions aloud after repeated "Read aloud" presses. Inputs and thresholds:
[adaptive-engine-plan.md](adaptive-engine-plan.md). Validation: 13 Python scenario tests, 41
Python-generated parity scenarios replayed in Dart, and phone tests showing that the suggestion
changes the run. Same input → same output (tested). No model, no confidence scores: an
explanation is the list of reason codes plus the stored records that triggered them.

### 3. Memory retrieval

Only `approved` memories of the patient are candidates. The phone never receives others,
and the conversation guard drops unknown, pending and foreign IDs. **New:** the engine's
ranked memory IDs now reach the games (`ActivityContent.preferredMemoryIds`), so photo
recall and familiar faces ask about the most relevant approved memories first. Relationships
and meaning come from what the caregiver entered. **No image recognition is used** to
identify people or places.

### 4. Trends and review prompts

- **Technique:** per-day descriptive statistics, compared with the same person's previous
  28 days. A prompt needs both a minimum overall change *and* the change on at least 66 %
  of days with data, so one bad session or day can never raise one. Too little data means
  "not evaluated", with the reason.
- **Human in the loop (new):** each prompt becomes a stored **review item** with a snapshot
  of its numbers. A managing caregiver confirms or dismisses it, and either decision needs a
  reason. Clinicians see only confirmed items; unconfirmed prompts are withheld from their
  analytics.
- **Not a diagnosis:** the wording on every item says so, and tests check that no
  diagnostic vocabulary appears in reports or dashboard text.
- **Evaluation:** behaviour is tested on synthetic data with known answers. There is no
  clinical validation of any kind.

### 6. Conversation

The LLM output is a JSON extraction (topic, people, places, intents, flags), never the
reply. Guards resolve every ID against the patient's approved data and OR the stop,
fatigue and distress flags with the deterministic detector, so a model can only add a stop,
never hide one. The patient-facing reply is a server template. Any failure (timeout,
malformed output, no consent, no key) falls back to the deterministic engine with a reason
code. The demo shows a fake model that says "no stop" being overruled.
**Live Gemini and the local LLM have not been run in this repository**, only faked.

### 7–8. Speech

| Language | ASR (Whisper) | Server TTS (Parler, model card) | Phone TTS | Verified here |
|---|---|---|---|---|
| English | ✅ | ✅ | depends on device | ASR `tiny` on one synthetic clip |
| Hindi | ✅ | ✅ | depends on device | no |
| Bengali | ✅ | ✅ | depends on device | no |
| Assamese | ✅ (low accuracy expected) | ✅ | depends on device | no |
| Nepali | ✅ | ✅ | depends on device | no |
| Bodo | ❌ | ✅ | unlikely | no |
| Manipuri (Meitei) | ❌ | ✅ | unlikely | no |
| Garo, Khasi, Mizo, Nagamese | ❌ | ❌ | unlikely | no |

- "✅" in the ASR and TTS columns means the model's own language table or model card lists
  the language. It does **not** mean it works well for older speakers in Assam.
- Failure behaviour (demonstrated): no consent → 409 `consent_required`; no model → 503
  `model_missing`; unsupported language → 422 `language_unsupported`. No transcript is ever
  made up, and the phone keeps large on-screen choices and text input.
- Components are separate: recognition (`speech/whisper.py`), understanding
  (`conversation/`) and synthesis (`speech/parler.py`, phone `speech/speech.dart`).
- Offline ASR on the phone is **not implemented**. Candidate for Bodo and Manipuri:
  AI4Bharat IndicConformer (MIT, NeMo). It needs on-device evaluation before any claim.

## What we deliberately did not do

- Train a model on synthetic data, or present any score as clinically meaningful.
- Use an LLM for safety, adaptation, trends or reports.
- Use image recognition to name people or relationships in photos.
- Claim offline speech or regional-language quality we have not measured.
