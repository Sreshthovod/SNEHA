"""The structured understanding every provider must return.

This schema is the ONLY thing a model may produce. It is strict (unknown fields are
rejected), bounded, and uses fixed enums wherever possible. Model output that does not
validate is discarded and the deterministic engine answers instead.

Nothing in here is trusted yet: app/conversation/guard.py checks every mention against
the user's own words and every ID against the patient's approved database records.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import MemoryKind

MAX_INPUT_CHARS = 1000

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
TagStr = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=40)]
IdStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=36)]


class Intent(StrEnum):
    GREETING = "greeting"
    FAREWELL = "farewell"
    ASK_TIME = "ask_time"
    ASK_DATE = "ask_date"
    ASK_ROUTINE = "ask_routine"
    TALK_ABOUT_PERSON = "talk_about_person"
    TALK_ABOUT_PLACE = "talk_about_place"
    TALK_ABOUT_MEMORY = "talk_about_memory"
    REQUEST_ACTIVITY = "request_activity"
    EXPRESS_FATIGUE = "express_fatigue"
    EXPRESS_DISTRESS = "express_distress"
    REQUEST_STOP = "request_stop"
    UNCLEAR = "unclear"
    OTHER = "other"


class Topic(StrEnum):
    FAMILY = "family"
    PLACE = "place"
    FOOD = "food"
    ROUTINE = "routine"
    FESTIVAL = "festival"
    MUSIC = "music"
    WELLBEING = "wellbeing"
    TIME = "time"
    MEMORY = "memory"
    ACTIVITY = "activity"
    SMALL_TALK = "small_talk"
    OTHER = "other"


class Clarification(StrEnum):
    NONE = "none"
    WHICH_PERSON = "which_person"
    WHICH_PLACE = "which_place"
    WHICH_ROUTINE = "which_routine"
    UNCLEAR_REQUEST = "unclear_request"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonMention(_Strict):
    mention: Short = Field(description="The words the person used, copied exactly.")
    memory_id: IdStr | None = Field(
        default=None, description="ID of a provided approved memory this refers to, if certain."
    )
    relationship_word: Short | None = Field(
        default=None,
        description="Relationship word ONLY if the person said it (e.g. 'my daughter').",
    )


class PlaceMention(_Strict):
    mention: Short
    memory_id: IdStr | None = None


class RoutineMention(_Strict):
    mention: Short
    routine_id: IdStr | None = None


class MemoryCandidate(_Strict):
    """Something the person shared that a caregiver might add to the Memory Bank."""

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    kind: MemoryKind
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = (
        None
    )


class ModelExtraction(_Strict):
    topic: Topic
    intents: list[Intent] = Field(min_length=1, max_length=5)
    people: list[PersonMention] = Field(default_factory=list, max_length=10)
    places: list[PlaceMention] = Field(default_factory=list, max_length=10)
    routines: list[RoutineMention] = Field(default_factory=list, max_length=10)
    relevant_memory_ids: list[IdStr] = Field(default_factory=list, max_length=10)
    topic_tags: list[TagStr] = Field(default_factory=list, max_length=10)
    fatigue_expressed: bool = Field(
        description="Only if the person explicitly says they are tired."
    )
    distress_expressed: bool = Field(
        description="Only if the person explicitly expresses fear, pain or needing help."
    )
    stop_requested: bool = Field(description="Only if the person explicitly asks to stop.")
    uncertain: bool
    clarification: Clarification = Clarification.NONE
    memory_candidates: list[MemoryCandidate] = Field(default_factory=list, max_length=3)
