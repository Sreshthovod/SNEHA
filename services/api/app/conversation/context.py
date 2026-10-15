"""The patient's APPROVED stored data that a conversation may refer to.

Only approved memories and active routines of THIS patient are loaded. This is both
the vocabulary the deterministic engine matches against and the (minimal) context sent
to an online model: IDs, kinds, titles and tags only, never descriptions or notes.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.care import RoutineItem
from app.models.enums import MemoryKind, MemoryStatus
from app.models.memories import MemoryItem
from app.personalization.config import PersonalizationConfig

# Words that never identify anything on their own (incl. the synthetic-fixture prefix).
STOPWORDS = frozenset(
    """a an the and or of at in on to for with my our your his her their is was were
    this that these those it its be been i me we you he she they them from by as
    synthetic old new very""".split()
)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def key_words(text: str) -> set[str]:
    return {w for w in words(text) if len(w) >= 3 and w not in STOPWORDS}


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    kind: MemoryKind
    title: str
    tags: tuple[str, ...]
    description: str | None
    has_photo: bool

    @property
    def keys(self) -> set[str]:
        return key_words(self.title) | {t.lower() for t in self.tags}

    def mentions_word(self, word: str) -> bool:
        """Does the STORED data contain this word (used to verify relationship words)?"""
        haystack = (
            key_words(self.title)
            | key_words(self.description or "")
            | {t.lower() for t in self.tags}
        )
        return word.lower() in haystack


@dataclass(frozen=True)
class RoutineEntry:
    id: str
    title: str
    local_time: str

    @property
    def keys(self) -> set[str]:
        return key_words(self.title)


@dataclass
class PatientContext:
    patient_id: str
    memories: list[MemoryEntry] = field(default_factory=list)
    routines: list[RoutineEntry] = field(default_factory=list)
    known_tags: frozenset[str] = frozenset()

    def memory(self, memory_id: str | None) -> MemoryEntry | None:
        return next((m for m in self.memories if m.id == memory_id), None)

    def routine(self, routine_id: str | None) -> RoutineEntry | None:
        return next((r for r in self.routines if r.id == routine_id), None)

    def for_prompt(self) -> dict:
        return {
            "approved_memories": [
                {"id": m.id, "kind": m.kind.value, "title": m.title, "tags": list(m.tags)}
                for m in self.memories
            ],
            "routines": [
                {"id": r.id, "title": r.title, "time": r.local_time} for r in self.routines
            ],
            "known_tags": sorted(self.known_tags),
        }


def load_context(
    db: Session, patient_id: str, cfg: PersonalizationConfig, limit: int = 200
) -> PatientContext:
    memories = [
        MemoryEntry(
            m.id,
            m.kind,
            m.title,
            tuple(t.lower() for t in (m.tags or [])),
            m.description,
            m.media_file_id is not None,
        )
        for m in db.scalars(
            select(MemoryItem)
            .where(MemoryItem.patient_id == patient_id, MemoryItem.status == MemoryStatus.APPROVED)
            .order_by(MemoryItem.created_at.desc())
            .limit(limit)
        )
    ]
    routines = [
        RoutineEntry(r.id, r.title, r.local_time)
        for r in db.scalars(
            select(RoutineItem)
            .where(RoutineItem.patient_id == patient_id, RoutineItem.is_active.is_(True))
            .order_by(RoutineItem.local_time)
        )
    ]
    tags = {t for m in memories for t in m.tags}
    for activity_tags in cfg.activity_interest_tags.values():
        tags.update(t.lower() for t in activity_tags)
    return PatientContext(patient_id, memories, routines, frozenset(tags))
