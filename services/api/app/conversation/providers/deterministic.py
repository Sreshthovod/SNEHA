"""Deterministic conversation understanding: keyword rules + matching against stored data.

Always available, offline, no model. It can only ever point at the patient's own
approved memories and routines, and every mention it reports is a word the person
actually said.

Keyword lists: English is the reviewed baseline. Hindi (hi), Assamese (as) and Bengali
(bn) entries are DRAFTS written without native-speaker review and must be checked
before use with patients.
"""

import re
import unicodedata

from app.conversation.context import PatientContext, key_words, words
from app.conversation.extraction import (
    Clarification,
    Intent,
    MemoryCandidate,
    ModelExtraction,
    PersonMention,
    PlaceMention,
    RoutineMention,
    Topic,
)
from app.models.enums import Language, MemoryKind

# English (reviewed) + DRAFT hi/as/bn. Multi-word entries match as phrases.
KEYWORDS: dict[Intent, list[str]] = {
    Intent.GREETING: [
        "hello",
        "hi",
        "hey",
        "namaste",
        "namaskar",
        "good morning",
        "good afternoon",
        "good evening",
        "नमस्ते",
        "नमस्कार",
        "নমস্কাৰ",
        "নমস্কার",
        "হ্যালো",
    ],
    Intent.FAREWELL: ["bye", "goodbye", "good night", "see you", "अलविदा", "शुभ रात्रि"],
    Intent.ASK_TIME: ["what time", "the time", "time is it", "समय", "কি সময়", "কটা বাজে", "বাজিছে"],
    Intent.ASK_DATE: [
        "what day",
        "what date",
        "which day",
        "today's date",
        "what is today",
        "तारीख",
        "তাৰিখ",
        "তারিখ",
    ],
    Intent.ASK_ROUTINE: [
        "what should i do",
        "what do i do now",
        "my routine",
        "what's next",
        "what is next",
        "schedule",
        "दिनचर्या",
    ],
    Intent.REQUEST_ACTIVITY: [
        "game",
        "play",
        "activity",
        "puzzle",
        "something to do",
        "खेल",
        "খেল",
        "খেলা",
    ],
    Intent.EXPRESS_FATIGUE: [
        "tired",
        "sleepy",
        "exhausted",
        "weary",
        "need rest",
        "need a rest",
        "want to rest",
        "थक",
        "नींद",
        "ভাগৰ",
        "টোপনি",
        "ক্লান্ত",
    ],
    Intent.EXPRESS_DISTRESS: [
        "scared",
        "afraid",
        "frightened",
        "help me",
        "pain",
        "hurts",
        "hurting",
        "i am lost",
        "i'm lost",
        "can't breathe",
        "cannot breathe",
        "chest",
        "i fell",
        "fell down",
        "dizzy",
        "panic",
        "don't feel well",
        "not feeling well",
        "unwell",
        "डर",
        "दर्द",
        "बचाओ",
        "मदद",
        "ভয়",
        "বিষ",
        "সহায়",
        "ব্যথা",
        "সাহায্য",
    ],
    Intent.REQUEST_STOP: [
        "stop",
        "enough",
        "no more",
        "i want to stop",
        "quit",
        "do this anymore",
        "don't want to do this",
        "don't want to continue",
        "रुको",
        "रुकिए",
        "बस करो",
        "बस",  # whole word only, see _WHOLE_WORD
        "बंद",
        "বন্ধ",
        "থামো",
        "থামুন",
        "বন্ধ করুন",
        "ৰখা",
        "ৰখক",
        "বন্ধ কৰক",
    ],
    Intent.TALK_ABOUT_MEMORY: [
        "remember",
        "used to",
        "when i was",
        "long ago",
        "in my youth",
        "याद",
        "মনত",
        "মনে",
    ],
}

RELATIONSHIP_WORDS = [
    "daughter",
    "son",
    "wife",
    "husband",
    "sister",
    "brother",
    "mother",
    "mom",
    "mum",
    "father",
    "dad",
    "aunt",
    "uncle",
    "grandson",
    "granddaughter",
    "grandchild",
    "niece",
    "nephew",
    "friend",
    "cousin",
    "बेटी",
    "बेटा",
    "माँ",
    "पिता",  # DRAFT
]

# "no" is deliberately absent: "No, I'm tired" is still tired.
_NEGATIONS = {"not", "never", "isn't", "aren't", "don't", "didn't", "am't", "nahi"}
# DRAFT hi/bn/as negations. They follow the word they negate ("मैं थका नहीं हूँ").
_INDIC_NEGATIONS = {unicodedata.normalize("NFC", w) for w in ("नहीं", "नही", "না", "নই", "নহয়", "নাই")}
_INDIC_NEGATABLE = {Intent.EXPRESS_FATIGUE}  # Indic distress stays un-negated (safe side)
# Indic keywords too short to match as substrings ("बस" is inside "बस्ती").
_WHOLE_WORD = {"बस"}
_PUNCT = ".,!?।;:\"'()"
_CANDIDATE_CUES = ("remember when", "used to", "when i was", "long ago")
_SENTENCE = re.compile(r"[^.!?।\n]+")


def _normalise(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").split())


def _indic_has(text: str, keyword: str, negatable: bool) -> bool:
    # NFC so "য়" typed as one code point or as য + nukta compares equal.
    text, keyword = unicodedata.normalize("NFC", text), unicodedata.normalize("NFC", keyword)
    if keyword in _WHOLE_WORD:
        return keyword in (w.strip(_PUNCT) for w in text.split())
    start = text.find(keyword)
    while start != -1:
        if not negatable:
            return True
        rest = text[start + len(keyword) :]
        after = rest.split()
        if rest and not rest[0].isspace():
            after = after[1:]  # the rest of the inflected word itself
        if not any(w.strip(_PUNCT) in _INDIC_NEGATIONS for w in after[:2]):
            return True
        start = text.find(keyword, start + 1)
    return False


def _has(text: str, tokens: list[str], keyword: str, negatable: bool | None = None) -> bool:
    """negatable=False (stop) ignores negation: over-triggering stop is the safe side.
    By default only English keywords are negatable."""
    if negatable is None:
        negatable = keyword.isascii()
    if not keyword.isascii():
        return _indic_has(text, keyword, negatable)  # substring: inflections share a stem
    kw = keyword.split()
    for i in range(len(tokens) - len(kw) + 1):
        if tokens[i : i + len(kw)] == kw:
            before = tokens[max(0, i - 2) : i]
            if negatable and any(b in _NEGATIONS or b.endswith("n't") for b in before):
                continue  # "I'm not tired"
            return True
    return False


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text)


def detect_intents(text: str) -> list[Intent]:
    norm = _normalise(text)
    tokens = _tokens(norm)
    found = []
    for intent, kws in KEYWORDS.items():
        if intent is Intent.REQUEST_STOP:
            negatable = False  # negation never cancels a stop request
        elif intent in _INDIC_NEGATABLE:
            negatable = True
        else:
            negatable = None
        if any(_has(norm, tokens, k, negatable) for k in kws):
            found.append(intent)
    # "I don't feel well" must not be read as negated distress.
    return found


class DeterministicProvider:
    name = "deterministic"

    def analyze(self, text: str, language: Language, context: PatientContext) -> ModelExtraction:
        norm = _normalise(text)
        tokens = _tokens(norm)
        said = set(words(norm))
        intents = detect_intents(text)

        people: list[PersonMention] = []
        places: list[PlaceMention] = []
        relevant: list[str] = []
        for memory in context.memories:
            hits = sorted(memory.keys & said)
            if not hits:
                continue
            relevant.append(memory.id)
            if memory.kind is MemoryKind.PERSON:
                people.append(PersonMention(mention=hits[0], memory_id=memory.id))
            elif memory.kind is MemoryKind.PLACE:
                places.append(PlaceMention(mention=hits[0], memory_id=memory.id))

        for rel in RELATIONSHIP_WORDS:
            if not _has(norm, tokens, rel):
                continue
            matches = [
                m for m in context.memories if m.kind is MemoryKind.PERSON and m.mentions_word(rel)
            ]
            mention = f"my {rel}" if f"my {rel}" in norm else rel
            resolved = matches[0].id if len(matches) == 1 else None
            if resolved and any(p.memory_id == resolved for p in people):
                continue
            people.append(PersonMention(mention=mention, memory_id=resolved, relationship_word=rel))
            if resolved and resolved not in relevant:
                relevant.append(resolved)

        routines = [
            RoutineMention(mention=sorted(r.keys & said)[0], routine_id=r.id)
            for r in context.routines
            if r.keys & said
        ]
        tags = sorted(t for t in context.known_tags if (" " in t and t in norm) or t in said)

        if people and Intent.TALK_ABOUT_PERSON not in intents:
            intents.append(Intent.TALK_ABOUT_PERSON)
        if places and Intent.TALK_ABOUT_PLACE not in intents:
            intents.append(Intent.TALK_ABOUT_PLACE)
        if not intents:
            intents = [Intent.UNCLEAR]

        candidates: list[MemoryCandidate] = []
        for sentence in _SENTENCE.findall(text):
            s = " ".join(sentence.split())
            if any(cue in s.lower() for cue in _CANDIDATE_CUES) and len(s.split()) >= 4:
                if not any(key_words(s) & m.keys for m in context.memories):
                    candidates.append(MemoryCandidate(title=s[:120], kind=MemoryKind.STORY))
            if len(candidates) == 3:
                break

        unresolved = [p for p in people if p.memory_id is None] + [
            p for p in places if p.memory_id is None
        ]
        clarification = Clarification.NONE
        if any(p.memory_id is None for p in people):
            clarification = Clarification.WHICH_PERSON
        elif intents == [Intent.UNCLEAR]:
            clarification = Clarification.UNCLEAR_REQUEST

        return ModelExtraction(
            topic=_topic(intents, people, places, routines, tags),
            intents=intents[:5],
            people=people[:10],
            places=places[:10],
            routines=routines[:10],
            relevant_memory_ids=relevant[:10],
            topic_tags=tags[:10],
            fatigue_expressed=Intent.EXPRESS_FATIGUE in intents,
            distress_expressed=Intent.EXPRESS_DISTRESS in intents,
            stop_requested=Intent.REQUEST_STOP in intents,
            uncertain=bool(unresolved) or intents == [Intent.UNCLEAR],
            clarification=clarification,
            memory_candidates=candidates,
        )


def _topic(intents, people, places, routines, tags) -> Topic:
    if Intent.EXPRESS_DISTRESS in intents or Intent.EXPRESS_FATIGUE in intents:
        return Topic.WELLBEING
    if people:
        return Topic.FAMILY
    if places:
        return Topic.PLACE
    if routines or Intent.ASK_ROUTINE in intents:
        return Topic.ROUTINE
    if Intent.ASK_TIME in intents or Intent.ASK_DATE in intents:
        return Topic.TIME
    if Intent.REQUEST_ACTIVITY in intents:
        return Topic.ACTIVITY
    if Intent.TALK_ABOUT_MEMORY in intents:
        return Topic.MEMORY
    if {"cooking", "food", "tea"} & set(tags):
        return Topic.FOOD
    if Intent.GREETING in intents or Intent.FAREWELL in intents:
        return Topic.SMALL_TALK
    return Topic.OTHER
