# Offline strategy and synchronisation

The patient may have no connectivity for days. **Everything the patient does must work
offline**, and nothing may be lost or double-counted when the phone reconnects.

## Two databases, explicit sync

- The phone has its own **SQLite** database. The server has **PostgreSQL**.
- They are **not** replicas and do **not** synchronise by themselves. The patient app runs
  an explicit sync: **push** its outbox, then **pull** the server change log.
- Sync is opportunistic (app start, after a session, connectivity regained) and safe to
  interrupt at any point.

## Ownership

Each entity has exactly one writer, so most conflicts cannot happen.

| Entity | Written by | Direction |
|---|---|---|
| Activity sessions, activity results | Device (or dashboard for supervised sessions) | push |
| Conversation records (metadata only) | Device | push |
| Personalization state | Device (rules engine) | push, and echoed back on pull |
| Memory items (approved only), memory relationships | Dashboard (caregivers) | pull |
| Routine items | Dashboard | pull |
| Activity catalog | Server (migrations) | pull |

## Identity

Records created offline get a **client-generated UUIDv4** that never changes. The server
accepts these IDs (`id` fields on sessions, results, conversations and memories). Each
installation has a stable random `install_id` stored in `app_meta`, sent as
`device_install_id`.

## Push: `POST /api/v1/sync/push`

```json
{
  "device_install_id": "…uuid…",
  "mutations": [
    {"mutation_id": "…uuid…", "entity_type": "activity_session", "data": {"id": "…", "started_at": "…", "status": "in_progress"}},
    {"mutation_id": "…uuid…", "entity_type": "activity_result",  "data": {"id": "…", "session_id": "…", "...": "..."}}
  ]
}
```

- Up to 200 mutations per request, processed **in order** (push a session before its
  results).
- Each mutation runs in its own savepoint and gets its own outcome; one bad record never
  fails the batch.
- Outcomes: `applied` · `duplicate` (already processed, safe to delete from the outbox) ·
  `conflict` (server state wins; see below) · `rejected` (invalid; keep it locally for
  inspection, do not retry blindly).
- **Idempotency, two layers.** (1) `mutation_id` receipts in `sync_mutations`: a replayed
  mutation returns `duplicate` without touching data. (2) Record IDs: an identical result
  under a new mutation ID is still a `duplicate`; a *different* result reusing an ID is a
  `conflict` (results are immutable).
- Requires a device session (role `patient`) and current `data_processing` consent.

### Conflict rules

| Entity | Rule |
|---|---|
| Activity result | Immutable. Same ID with different content → `conflict` |
| Session | Can move `in_progress` → ended once; a different end later → `conflict` |
| Conversation record | Insert once; may be closed (`ended_at`) once |
| Personalization state | Last-writer-wins by device `state_updated_at`; an older push → `conflict` |

## Pull: `GET /api/v1/sync/pull?since=<seq>&limit=<n>`

- The server appends every change a device must see to `sync_changes` with a monotonically
  increasing `seq`. Clients store `next_since` and pass it back. Using `seq` instead of
  timestamps means clock skew cannot drop changes.
- On PostgreSQL, writers to the change log take a transaction-scoped advisory lock, so
  `seq` order equals commit order. Without it, a device could read seq 7 before seq 6
  commits and skip 6 forever.
- Each change carries the **current** record (`data`) or `null` for deletes. Memory items
  that are not approved are always delivered as deletes, so pending, rejected and deleted
  memories never reach the phone. Deleted memories leave only an ID tombstone.
- `has_more: true` → pull again immediately with the new `since`.
- Changes are filtered to the device's own patient plus global entries (the catalog).

## Device implementation

- **Local database** (`lib/data/local/local_database.dart`): versioned, append-only
  migrations. It holds profiles, catalog (with specs), approved memories (with cached
  photos), routines, preferences, sessions, results, outbox, sync state and settings.
- **Recording**: each local record and its outbox row are written in one SQLite
  transaction.
- **Push**:
  - the outbox goes in order, 200 at a time
  - `applied` and `duplicate` entries are cleared
  - network errors never count as attempts
  - server errors back off exponentially (30 s doubling to 6 h); after 8 attempts the
    entry is kept and marked **needs attention**, never deleted
  - conflicts and rejections are kept and listed on the sync screen with a plain
    explanation and "Try again" where retrying makes sense
- **Pull**: page by page; each page and its cursor are applied in one transaction, so a
  restart mid-sync resumes cleanly. Tombstones delete local copies. **An older version of
  an approved memory never replaces a newer local copy.**
- **Personalization offline**: the Dart port of the engine runs on local results (see
  `packages/shared_docs/personalization-rules.md`). When online, `POST
  /activities/next` is used and the result says which source chose it.

## What works offline and what needs a connection

| Feature | Offline | Needs connection |
|---|---|---|
| All six games + story time, using approved memories and cached photos | ✅ | |
| Recording results, tiredness and enjoyment | ✅ (outbox) | sharing them |
| Adaptive difficulty and "Suggested for you" | ✅ (on-phone engine) | server suggestions (they also use caregiver observations) |
| Local progress ("What I have done") | ✅ | |
| Simple conversation helper | ✅ (deterministic, on phone) | AI understanding, memory retrieval, suggestions (`/conversation/analyze`) |
| Read aloud | ✅ if the phone has a voice for the language | server TTS (optional) |
| Voice input | | ✅ (`/speech/transcribe`, model and consent required) |
| Pairing, consent refresh, new memories, photos, catalog, preferences | | ✅ |
| Caregiver dashboard, analytics, PDF reports | | ✅ |

Caregiver observations are not synced to the phone (privacy: the note text stays on the
server), so the on-phone engine cannot react to them. The server engine does, whenever the
phone is online.
