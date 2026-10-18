# Fatigue-aware safety: inspection and plan

Date: 2026-10-18. Builds on the fatigue, stop and in-activity work in
[original-problem-alignment-audit.md](original-problem-alignment-audit.md) (F1, F3),
[safety-and-privacy.md](safety-and-privacy.md) and [adaptive-engine-plan.md](adaptive-engine-plan.md).
No second safety or session system is added.

## 1. Traced paths

### Caregiver reports fatigue

| Path | Steps today | Works? |
|---|---|---|
| On the patient's phone (Caregiver button in an activity, or "For caregivers" → Report tiredness) | stored in `fatigue_reports` + outbox in one transaction → in-session policy at once (mild: at most 1 more round, hints sooner; very tired: end, rest) → `fatigue_reported` + `adaptation` events → engine sees it offline (mild: easiest gentle activity; very tired: rest) → pushed as a fatigue observation with level | ✅ works, tested |
| On the dashboard | observation with level → change log → the phone receives level and time at its **next sync** → a running activity checks for new reports at each round → engine sees it | ⚠️ the phone syncs only at app start, after an activity and on demand, so **a running activity never receives a dashboard report**; the dashboard cannot tell whether the phone has it ("reaches the phone when it next syncs" was the only feedback) |
| Phone offline when the caregiver reports on the phone | applied locally at once; queued | ⚠️ the confirmation said "Thank you…" without saying the report has not been shared yet |

### The person asks for a break or to stop

| Control | Steps today | Works? |
|---|---|---|
| Stop (button or system back) | pauses the timer, asks "Stop this activity?" once, then ends: `stop_requested` + `adaptation(end_session, STOP_REQUESTED)`, session `user_stopped`; the engine's next suggestion respects stop when requested | ⚠️ the confirmation's **filled (primary) button was "Keep going"**, which nudges the person to continue |
| Pause ("I need a moment") | timer stops, round hidden, "Carry on" resumes; events `paused`/`resumed` | ✅ |
| I'm tired | ends gently, rest offered, result marked, session `fatigue_detected` | ✅ |
| Phone goes to the background (home button, call, screen off) mid-activity | **the activity timer kept running**, and the run continued on return as if nothing happened | ❌ |
| App killed mid-activity | the session stays `in_progress` on the phone and server for ever | ❌ never marked interrupted |
| Finishing twice (double tap, retry) | the runner guards it; the server refuses a second end (409); **the phone's recorder rewrote the local session and queued a second end** if called twice | ⚠️ |

## 2. Session safety policy (existing model, named once)

| State | Represented by (existing) | Who/what causes it |
|---|---|---|
| Normal activity | session `in_progress`, runner active | start |
| Reduced cognitive demand | `adaptation` events (`shorten`, `show_hint`), engine `LOW_EFFORT_FOR_FATIGUE` / hint support | policy, engine |
| Break offered | runner rest dialog (`offer_break`), engine action `break` | policy, engine |
| Break in progress | runner paused (`paused` event; timer stopped) | the person (Pause), **or the phone leaving the screen (new)** |
| Patient requested stop | session `abandoned` + `user_stopped`; `stop_requested` event | the person |
| Session completed | session `completed` | last round, or shortened run |
| Session interrupted | session `abandoned` + **`timeout`** (existing enum value, newly used) | app closed mid-activity; closed at next start |
| Caregiver-reported fatigue | `fatigue_reports` / fatigue observation with level; `fatigue_reported` event | caregiver |
| Unavailable observations | missing scores/metrics are neutral; engine `COLD_START_DEFAULT`, `MISSING_DATA_NOT_COUNTED_AS_ERROR` | — |

Priority (enforced in `session_policy.dart` and `engine.py`/`engine.dart`):
1. Stop → end now. 2. Break (Pause / I'm tired / very tired) → pause or rest.
3. Caregiver fatigue → less demand, rest offered. 4. Ordinary adaptation. 5. Missing data is
unknown. 6. An ended session never restarts: a new run is always a new, explicit session.

## 3. Corrections in this phase

| # | Change | Where |
|---|---|---|
| C1 | Stop confirmation: "Yes, stop" is the primary (filled) button; one short question, never repeated | runner |
| C2 | Leaving the screen pauses the run (timer stops, `paused` with `source: system`); coming back shows the pause screen and nothing continues until the person chooses "Carry on" | runner (`AppLifecycleState`) |
| C3 | Sessions left `in_progress` (app killed) are closed as `timeout` (interrupted) at the next app start, excluding nothing active; synced normally | recorder + app start |
| C4 | Ending a session twice is a no-op on the phone (no second local write, no duplicate mutation) | recorder |
| C5 | During an activity, while online, the phone syncs in the background at most once a minute at round boundaries, so a dashboard fatigue note reaches the running activity; never blocks the screen | runner |
| C6 | Honest delivery status on the dashboard for each fatigue note: "On the phone since …", "Waiting for the phone (last synced …)", "No phone paired", or "Reported on the phone". The server records each device's last pulled change (migration 0014) | API + dashboard |
| C7 | Honest phone feedback: a caregiver report made offline says it is saved on the phone and will be shared when online | caregiver screen / runner |

Not changed: authorization (observations remain caregiver/clinician-only; the phone receives
level and time, never the note), engine rules, timers of the in-activity policy.

## 4. Status (2026-10-18): implemented and tested

| # | Status | Tests |
|---|---|---|
| C1 stop is the primary choice, asked once, nothing decided after it | ✅ | `test/safety/session_safety_test.dart` "stop: one short question…" |
| C2 leaving the screen pauses; background time is pause time; waits for "Carry on" | ✅ | "leaving the screen pauses the run…", "a finished run does not restart…" |
| C3 sessions left running are closed as interrupted (`timeout`) at the last recorded step, once | ✅ | "a session the app left running…", home sync test |
| C4 ending twice writes once; a stop is never overwritten (phone; the server already refused) | ✅ | "ending twice is written once…" |
| C5 background sync during an activity (online, ≤ 1/min) brings a dashboard note into the running activity | ✅ | "a dashboard 'very tired' note reaches the running activity…" |
| C6 delivery status per tiredness note (migration 0014, `GET /patients/{id}/fatigue-delivery`) | ✅ | `test_caregiver_fatigue.py` (waiting → sent, no phone, from phone, privacy); dashboard `alignment.test.tsx` |
| C7 honest offline wording on the phone | ✅ | `caregiver_home_test.dart` |

Also found and fixed: `test_offline_recording_then_synchronisation` used the UTC date for an
India-time patient and failed every day between 18:30 and 24:00 UTC (test-only fix).

## 5. Remaining limits

- "Sent to the phone" means the phone fetched the change; it does not prove an activity was
  running or that the person saw anything. The phone only fetches while online.
- No push channel: a dashboard note reaches a running activity within about a minute only if
  the phone is online; otherwise at its next sync. The on-phone Caregiver button acts at once.
- Interrupted sessions are closed when the app next opens the home screen for that person,
  not at the moment the app was killed.
- Lifecycle behaviour is tested by simulating Android lifecycle states in widget tests; it has
  not been tried on the real phone (home button, incoming call, screen lock).
