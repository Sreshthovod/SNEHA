# Glossary

| Term | Meaning |
|---|---|
| Patient | The older adult using the phone app. Has a `patient_profile`; signs in by device pairing |
| Caregiver | Family member or carer linked by a `caregiver_relationship` |
| Managing caregiver | Caregiver with `can_manage`: curates the Memory Bank, manages access and consent |
| Clinician | Verified professional with a time-limited, read-only `clinician_access_grant` |
| Memory Bank | Caregiver-approved personal memories (people, places, events, objects, stories) with optional photos |
| Proposal | A memory awaiting approval (`pending_approval`). Never shown to the patient |
| Session | One sitting of activities (`in_progress` → `completed` or `abandoned`) |
| Result | Immutable outcome of one activity in a session |
| Fatigue end | A session ended by the fatigue rules (`end_reason = fatigue_detected`) |
| Observation | A caregiver's descriptive note about the patient's day. Not a diagnosis |
| Report | Descriptive 8–9 day summary for caregivers and granted clinicians |
| Mutation | One device change pushed during sync, identified by `mutation_id` |
| Change log | Server's ordered list (`seq`) of changes devices pull |
| Synthetic | Clearly fictional demo or test data. Real patient data never appears in the repository |
