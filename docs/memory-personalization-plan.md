# Memory-based personalization: inspection and plan

Date: 2026-10-18. Scope: make caregiver-approved memories drive the patient's activities,
using the existing models, sync, engine, runner and recording. No new AI/ML service.

## 1. What exists (inspected)

| Area | Where | State |
|---|---|---|
| Memory model | `services/api/app/models/memories.py` (`MemoryItem`: kind person/place/event/object/story, title, description, approx_year, tags, media_file_id, status, version) | ✅ Works |
| Memory links | `memory_relationships` (`person_in`, `located_at`, `part_of`, `related_to`) + `/memory-relationships` API | ⚠️ API and sync work, **no dashboard UI**, nothing on the phone uses links |
| Relationship to the patient ("granddaughter") | — | ❌ **Missing.** Only free text in title/description/tags, so no activity can use it reliably |
| Photo upload | `/patients/{id}/media` (type from bytes, consent required), protected download | ✅ Works |
| Approval workflow | Managing caregiver's memories auto-approved; helpers' proposals pending; approve/reject with `expected_version` | ✅ Works |
| Only approved memories leave the server for the phone/AI | `services/sync.py::_payload` (pending/rejected sent as delete), conversation guard | ✅ Works, tested |
| Duplicate submissions | Server rejects a reused client `id` (409 `id_conflict`) | ⚠️ The dashboard does **not** send a client id, so a double submit creates two memories |
| Failed upload | Dashboard uploads the photo, then creates the memory | ⚠️ If the second step fails, the photo stays orphaned (known O4); the form shows the error |
| Phone cache | `memories` table (approved only) + `local_photo_path` set only when the photo file is downloaded (`media_cache.dart`) | ✅ `MemoryItem.hasPhoto` = "photo is on this phone", so availability is honest |
| Engine memory ranking | `memory_retrieval.py` / Dart `LocalFacts.content`: interest-tag matches, avoids recently used, thresholds per activity | ✅ Works; ranked IDs reach games via `preferredMemoryIds` (added in the alignment pass) |
| Photo recall | `memory_games.dart`: approved photo → choose its title; year as hint | ✅ Uses memories |
| Familiar faces | approved person photos → choose the photo for a name | ✅ Uses memories; ⚠️ cannot say who the person is to the patient |
| Story time | `story_time_screen.dart`: shows **all** approved memories in storage order with 3 generic rotating prompts | ⚠️ Ignores the engine's choice, ignores links/kind; records only a `memories_viewed` count, **no events** |
| Picture pairs, sort into groups, name the object | `everyday_games.dart`: bundled icons/categories only | ❌ Never personal, even when approved photos exist |
| Daily sequence | uses the patient's own routines when ≥ 3 | ✅ Personal (routines, not memories) |
| Session record of memories used | `activity_events` / results | ❌ **Missing.** Nothing records which memory a round showed |

## 2. Gaps and decisions

| # | Gap | Decision |
|---|---|---|
| M1 | No structured "who is this to the patient" | Add nullable `memory_items.relationship` (≤ 60 chars, **person memories only**, caregiver-entered). Migration 0012. Needed because tags/description are free text and cannot drive a hint safely. Never inferred from photos |
| M2 | Activities don't share one content builder | New pure Dart module `lib/activities/memory_content.dart`: from the cached approved memories (+ links) decides per activity whether **personal** content is possible, builds the items, and returns the memory IDs used and reason codes. Games consume it; the logic stays separate from widgets |
| M3 | Story time is generic | Guided prompts built only from stored fields (kind, title, year, relationship, linked memories); engine's preferred memories first; falls back to the generic prompt when a field is missing |
| M4 | Pairs and sorting ignore approved photos | Picture pairs: use cached approved photos as the pictures when there are enough (else bundled). Sort into groups: "person or place?" by the caregiver-set `kind`, when ≥ 2 kinds have ≥ 2 photos each (else bundled). No new game |
| M5 | Memory use not recorded | `EventData` gains optional `memory_ids` (activity start: all used), `memory_id` (per round/answer) and `content_source` (`personal` / `generic`). Additive API change. Story time records events too. Dashboard timeline shows titles (caregivers; clinicians have no Memory Bank access and see only "a family memory") |
| M6 | Caregiver can't see what a memory does | Memory card shows: shared with the phone or not (and why), and which activities it can appear in, computed by the same published rules |
| M7 | Duplicate submit | Dashboard sends a client UUID per form; a 409 `id_conflict` after a retry is treated as "already saved" |
| M8 | Links not editable | Small "Linked memories" control on the card (uses existing API) |

Not done (documented): object/category metadata beyond `kind`; using `relationship` inside the conversation guard; any image recognition.

## 3. Rules (deterministic, published)

Personal content is used only when the phone has the approved data **and** the photo file
where one is needed; otherwise the bundled generic version runs and says so
(`GENERIC_CONTENT_FALLBACK`).

| Activity | Personal when | Uses | Generic fallback |
|---|---|---|---|
| Photo recall | ≥ 2 approved memories with cached photos (distinct titles) | photo + title; year as hint | none: activity unavailable (empty state) |
| Familiar faces | ≥ 2 approved **person** memories with cached photos | photo + title; relationship as hint if entered | none: unavailable |
| Picture pairs | ≥ pairs-needed approved memories with cached photos | the photos as cards | bundled pictures |
| Sort into groups | ≥ 2 kinds (person/place/event/object) with ≥ 2 cached photos each | photo → its kind | bundled categories |
| Story time | ≥ 1 approved memory (photo optional) | title, description, year, relationship, links | generic prompt per memory when fields are missing; empty state when none |
| Name the object, daily sequence | unchanged | bundled / routines | — |

Reason codes recorded in `activity_started`: `PERSONAL_PHOTOS_USED`, `PERSONAL_PEOPLE_USED`,
`MEMORY_KIND_SORTING`, `GUIDED_STORY_FROM_APPROVED_FIELDS`, `RELATIONSHIP_HINT_AVAILABLE`,
`ENGINE_PREFERRED_MEMORIES_FIRST`, `GENERIC_CONTENT_FALLBACK`, `NOT_ENOUGH_CACHED_PHOTOS`.

## 4. Order of work (each step keeps the app runnable)

1. Server: migration 0012 (`relationship`), schemas, event fields; tests.
2. Dashboard: relationship field, client id, availability panel, links, timeline titles; tests.
3. Phone (after the parallel UI redesign of the same files finished): local schema v6,
   `memory_content.dart`, games, story time, event recording; tests.
4. Docs: this file, implementation progress, architecture.

Status is tracked in [implementation-progress.md](implementation-progress.md).

## 5. Status (2026-10-18)

| # | Status | Where | Tests |
|---|---|---|---|
| M1 relationship | ✅ migration 0012; API create/correct/out; person-only (422 otherwise; cleared when re-typed); synced; phone schema v6 | `models/memories.py`, `schemas/memories.py`, `routes/memories.py`, phone `models.dart`, `local_database.dart`, `sync_service.dart` | `test_memories.py::test_relationship_…`, phone sync test |
| M2 content rules | ✅ `lib/activities/memory_content.dart`; activities report `contentChoice` (personal or generic + reasons); rounds carry `memoryIds` | games, `activity.dart` | `test/memory/memory_activities_test.dart` |
| M3 guided story | ✅ engine order, prompts from relationship, links, type and title only; general prompt otherwise; events recorded | `story_time_screen.dart` | story prompt + story recording tests |
| M4 pairs and sorting | ✅ family photos as pairs (≥ 3 cached); "person or place?" sorting by `kind` (≥ 2 types × 2 photos); bundled fallback with reasons | `everyday_games.dart`, `pairs_round.dart` | pairs/sorting tests; visual QA |
| M5 recording | ✅ `memory_ids`, `memory_id`, `content_source` on events; server refuses another patient's memory, keeps a deleted one; round events now carry their own round index | `schemas/events.py`, `services/sync.py`, runner | `test_activity_events.py`, phone recording tests |
| M6 caregiver view | ✅ "How SNEHA uses this": phone status, activities with thresholds, links | `MemoriesSection.tsx`, `lib/memoryUse.ts` | `memory-personalization.test.tsx` |
| M7 duplicate submit | ✅ client UUID; a 409 `id_conflict` on retry is shown as saved | `MemoriesSection.tsx` | same |
| M8 links | ✅ add and remove links on the card (existing API) | same | same |
| Phone refuses non-approved memories | ✅ added defensively: a pulled memory that is not approved or not this patient's is treated as a delete | `sync_service.dart` | phone sync test |

**Still open:** a phone-side signal of *which* photos are actually cached is not reported to the
dashboard (the server cannot know, so the card says "downloads at its next sync"). Object
sub-categories beyond `kind` are not modelled. The conversation guard does not use
`relationship` yet. New patient strings are English only. Orphaned photos after a failed
create (O4) remain.
