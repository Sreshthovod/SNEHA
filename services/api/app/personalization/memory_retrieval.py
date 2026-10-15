"""Tag- and entity-based retrieval over the APPROVED Memory Bank.

Only caregiver-approved memories are ever returned. Nothing is invented or inferred:
a memory matches because one of its stored tags, its kind, or a stored relationship
links it to the query. Scoring is deterministic and every match says why.

Embedding-based retrieval can be added later behind the same `retrieve` signature.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.activities import ActivityRecommendation
from app.models.care import RoutineItem
from app.models.enums import MemoryKind, MemoryStatus
from app.models.memories import MemoryItem, MemoryRelationship
from app.personalization.config import PersonalizationConfig
from app.personalization.engine import ContentAvailability


@dataclass
class MemoryMatch:
    memory: MemoryItem
    score: int
    matched_tags: list[str] = field(default_factory=list)
    via_relationship_to: list[str] = field(default_factory=list)
    recently_used: bool = False


def _norm(tags: Iterable[str]) -> set[str]:
    return {t.strip().lower() for t in tags if t and t.strip()}


def recently_used_memory_ids(db: Session, patient_id: str, last_n: int) -> set[str]:
    if last_n <= 0:
        return set()
    recs = db.scalars(
        select(ActivityRecommendation.content_refs)
        .where(ActivityRecommendation.patient_id == patient_id)
        .order_by(ActivityRecommendation.created_at.desc())
        .limit(last_n)
    )
    used: set[str] = set()
    for refs in recs:
        used.update((refs or {}).get("memory_item_ids", []))
    return used


def retrieve(
    db: Session,
    patient_id: str,
    *,
    tags: Iterable[str] = (),
    kind: MemoryKind | None = None,
    with_photo: bool = False,
    memory_ids: Iterable[str] = (),
    avoid_ids: set[str] | None = None,
    limit: int = 10,
) -> list[MemoryMatch]:
    """Return approved memories ranked by explicit matches.

    Score: +10 per matched tag, +8 if explicitly named by ID (e.g. resolved from a
    conversation), +3 if linked by a stored relationship to a matched memory,
    +2 if it has a photo, -5 if used in a recent recommendation. Ties: newest first, then ID.
    """
    query = select(MemoryItem).where(
        MemoryItem.patient_id == patient_id, MemoryItem.status == MemoryStatus.APPROVED
    )
    if kind is not None:
        query = query.where(MemoryItem.kind == kind)
    if with_photo:
        query = query.where(MemoryItem.media_file_id.is_not(None))
    memories = list(db.scalars(query))
    wanted = _norm(tags)
    named = set(memory_ids)
    avoid = avoid_ids or set()

    matches: dict[str, MemoryMatch] = {}
    for memory in memories:
        matched = sorted(wanted & _norm(memory.tags or []))
        score = 10 * len(matched) + (8 if memory.id in named else 0)
        matches[memory.id] = MemoryMatch(memory, score, matched)

    seeds = [m.memory.id for m in matches.values() if m.score > 0]
    if seeds:
        links = db.scalars(
            select(MemoryRelationship).where(
                MemoryRelationship.patient_id == patient_id,
                or_(
                    MemoryRelationship.from_memory_id.in_(seeds),
                    MemoryRelationship.to_memory_id.in_(seeds),
                ),
            )
        )
        for link in links:
            for this, other in (
                (link.from_memory_id, link.to_memory_id),
                (link.to_memory_id, link.from_memory_id),
            ):
                if this in seeds and other in matches and other not in seeds:
                    matches[other].score += 3
                    matches[other].via_relationship_to.append(this)

    for match in matches.values():
        if match.memory.media_file_id:
            match.score += 2
        if match.memory.id in avoid:
            match.score -= 5
            match.recently_used = True

    ranked = sorted(
        matches.values(),
        key=lambda m: (-m.score, -m.memory.created_at.timestamp(), m.memory.id),
    )
    return ranked[:limit]


def content_for_activities(
    db: Session,
    patient_id: str,
    interests: Iterable[str],
    cfg: PersonalizationConfig,
    context_memory_ids: Iterable[str] = (),
    context_tags: Iterable[str] = (),
) -> dict[str, ContentAvailability]:
    """Personal content each Memory-Bank (or routine) activity could use right now."""
    rules = cfg.memory
    avoid = recently_used_memory_ids(db, patient_id, rules.recent_use_recommendations)
    # Topics from the current conversation also select memories (the engine scores them
    # separately from approved interests).
    interest_tags = sorted({*interests, *context_tags})
    named = list(context_memory_ids)

    def pick(kind: MemoryKind | None, with_photo: bool, minimum: int) -> ContentAvailability:
        found = retrieve(
            db,
            patient_id,
            tags=interest_tags,
            kind=kind,
            with_photo=with_photo,
            memory_ids=named,
            avoid_ids=avoid,
            limit=max(rules.items_per_activity, minimum),
        )
        matched = sorted({t for m in found for t in m.matched_tags})
        ids = tuple(m.memory.id for m in found[: rules.items_per_activity])
        return ContentAvailability(
            len(found) >= minimum, ids if len(found) >= minimum else (), (), tuple(matched)
        )

    routines = list(
        db.scalars(
            select(RoutineItem.id)
            .where(RoutineItem.patient_id == patient_id, RoutineItem.is_active.is_(True))
            .order_by(RoutineItem.local_time)
        )
    )
    personal_routines = len(routines) >= rules.min_routine_items
    return {
        "photo-recall": pick(None, True, rules.min_photo_memories),
        "familiar-faces": pick(MemoryKind.PERSON, True, rules.min_person_photo_memories),
        "story-time": pick(None, False, rules.min_story_memories),
        # Bundled sequences always exist; the patient's own routines are preferred when enough.
        "daily-sequence": ContentAvailability(
            True,
            (),
            tuple(routines[: rules.items_per_activity]) if personal_routines else (),
            ("routine",) if personal_routines else (),
        ),
    }
