"""Validate a provider's extraction against reality before anything is used.

Rules (applied to EVERY provider, including the deterministic one):
- A mention survives only if it is the person's own words (found in their message).
- Every memory/routine ID must be one of THIS patient's approved memories / active
  routines (the context); anything else is dropped. Kinds must match.
- A relationship word is a stored fact only if the person said it AND the stored,
  approved memory contains it. Otherwise it is reported as an uncertain interpretation,
  never as a fact.
- Topic tags must be known tags (stored memory tags or activity interest tags).
- Memory candidates must be grounded in the person's words, must not duplicate an
  existing memory, and are never saved automatically.
- Any text with diagnostic or decline language is dropped.
- Distress, fatigue and stop are OR-ed across the model's flags, the model's intents and
  the deterministic keyword detector, so a model can never hide an explicit safety signal.
"""

import re
from dataclasses import dataclass, field

from app.conversation.context import PatientContext, key_words
from app.conversation.extraction import Clarification, Intent, ModelExtraction
from app.conversation.providers.deterministic import detect_intents
from app.models.enums import MemoryKind

_DIAGNOSTIC = re.compile(
    r"dementia|alzheimer|diagnos|cognitive|cognition|impair|declin|deteriorat|memory loss|"
    r"\bmci\b|disease|disorder|severity|symptom|मनोभ्रंश|স্মৃতিভ্ৰংশ|স্মৃতিভ্রংশ",
    re.IGNORECASE,
)


def is_diagnostic(text: str | None) -> bool:
    return bool(text) and bool(_DIAGNOSTIC.search(text))


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").split())


@dataclass
class GuardedPerson:
    mention: str
    memory_id: str | None
    relationship_word: str | None  # set only when it is a stored fact


@dataclass
class GuardedPlace:
    mention: str
    memory_id: str | None


@dataclass
class GuardedRoutine:
    mention: str
    routine_id: str | None


@dataclass
class Uncertain:
    type: str
    mention: str
    note: str


@dataclass
class GuardedCandidate:
    title: str
    kind: MemoryKind
    description: str | None


@dataclass
class Guarded:
    topic: str
    intents: list[Intent]
    people: list[GuardedPerson] = field(default_factory=list)
    places: list[GuardedPlace] = field(default_factory=list)
    routines: list[GuardedRoutine] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    fatigue: bool = False
    distress: bool = False
    stop: bool = False
    uncertain: bool = False
    clarification: Clarification = Clarification.NONE
    uncertain_interpretations: list[Uncertain] = field(default_factory=list)
    candidates: list[GuardedCandidate] = field(default_factory=list)
    dropped: int = 0


def _grounded(phrase: str, message: str) -> bool:
    return bool(phrase) and _norm(phrase) in _norm(message)


def _mostly_grounded(text: str, message: str, threshold: float = 0.7) -> bool:
    keys = key_words(text)
    if len(keys) < 2:
        return False
    said = key_words(message)
    return len(keys & said) / len(keys) >= threshold


def apply_guard(extraction: ModelExtraction, message: str, context: PatientContext) -> Guarded:
    g = Guarded(topic=extraction.topic.value, intents=list(dict.fromkeys(extraction.intents)))
    allowed_ids: list[str] = []

    def keep_memory(memory_id: str | None, kind: MemoryKind | None) -> str | None:
        memory = context.memory(memory_id)
        if memory_id is not None and (
            memory is None or (kind is not None and memory.kind is not kind)
        ):
            g.dropped += 1
            return None
        return memory.id if memory else None

    for p in extraction.people:
        if not _grounded(p.mention, message) or is_diagnostic(p.mention):
            g.dropped += 1
            continue
        memory_id = keep_memory(p.memory_id, MemoryKind.PERSON)
        relationship = None
        if p.relationship_word:
            stored = context.memory(memory_id)
            if (
                _grounded(p.relationship_word, message)
                and stored
                and stored.mentions_word(p.relationship_word)
            ):
                relationship = p.relationship_word.lower()
            else:
                g.uncertain_interpretations.append(
                    Uncertain(
                        "relationship",
                        p.mention,
                        "This relationship is not recorded in the approved Memory Bank.",
                    )
                )
        if memory_id is None:
            g.uncertain_interpretations.append(
                Uncertain("person", p.mention, "Could not be matched to an approved memory.")
            )
        else:
            allowed_ids.append(memory_id)
        g.people.append(GuardedPerson(p.mention, memory_id, relationship))

    for p in extraction.places:
        if not _grounded(p.mention, message) or is_diagnostic(p.mention):
            g.dropped += 1
            continue
        memory_id = keep_memory(p.memory_id, MemoryKind.PLACE)
        if memory_id is None:
            g.uncertain_interpretations.append(
                Uncertain("place", p.mention, "Could not be matched to an approved memory.")
            )
        else:
            allowed_ids.append(memory_id)
        g.places.append(GuardedPlace(p.mention, memory_id))

    for r in extraction.routines:
        if not _grounded(r.mention, message):
            g.dropped += 1
            continue
        routine = context.routine(r.routine_id)
        if r.routine_id is not None and routine is None:
            g.dropped += 1
        if routine is None:
            g.uncertain_interpretations.append(
                Uncertain("routine", r.mention, "Could not be matched to a stored routine.")
            )
        g.routines.append(GuardedRoutine(r.mention, routine.id if routine else None))

    for memory_id in extraction.relevant_memory_ids:
        if context.memory(memory_id) is None:
            g.dropped += 1
        else:
            allowed_ids.append(memory_id)
    g.memory_ids = list(dict.fromkeys(allowed_ids))[:10]

    tags = [t for t in extraction.topic_tags if t in context.known_tags]
    g.dropped += len(extraction.topic_tags) - len(tags)
    g.topic_tags = list(dict.fromkeys(tags))

    existing = [m.keys for m in context.memories]
    for c in extraction.memory_candidates:
        if not _mostly_grounded(c.title, message) or is_diagnostic(c.title):
            g.dropped += 1
            continue
        if any(len(key_words(c.title) & keys) >= 2 for keys in existing):
            continue  # already in the Memory Bank
        description = (
            c.description
            if c.description
            and _mostly_grounded(c.description, message)
            and not is_diagnostic(c.description)
            else None
        )
        g.candidates.append(GuardedCandidate(c.title, c.kind, description))

    # Model flags, model intents and keywords can each only ESCALATE a safety signal.
    signals = set(detect_intents(message)) | set(extraction.intents)
    g.distress = extraction.distress_expressed or Intent.EXPRESS_DISTRESS in signals
    g.fatigue = extraction.fatigue_expressed or Intent.EXPRESS_FATIGUE in signals
    g.stop = extraction.stop_requested or Intent.REQUEST_STOP in signals
    for flag, intent in (
        (g.distress, Intent.EXPRESS_DISTRESS),
        (g.fatigue, Intent.EXPRESS_FATIGUE),
        (g.stop, Intent.REQUEST_STOP),
    ):
        if flag and intent not in g.intents:
            g.intents.append(intent)
    if g.distress:
        g.topic = "wellbeing"

    g.uncertain = extraction.uncertain or bool(g.uncertain_interpretations)
    g.clarification = extraction.clarification
    if g.clarification is Clarification.NONE and any(p.memory_id is None for p in g.people):
        g.clarification = Clarification.WHICH_PERSON
    return g
