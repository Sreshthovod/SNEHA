from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import Language
from app.schemas.base import RecordId, RequestModel


class ProviderStatusOut(BaseModel):
    name: str
    configured: bool
    available: bool
    model: str | None
    languages: list[str]
    detail: str


class LanguageSupport(BaseModel):
    language: Language
    speech_recognition: bool
    speech_synthesis: bool


class SpeechStatus(BaseModel):
    asr: ProviderStatusOut
    tts: ProviderStatusOut
    languages: list[LanguageSupport]
    touch_alternative: str = (
        "Every voice feature has a touch alternative; text always stays on screen."
    )


class TranscriptionOut(BaseModel):
    """The transcript is returned to the caller only. It is never stored or logged."""

    text: str
    language: Language
    provider: str
    model: str
    confidence: float | None = Field(description="Mean model probability (0–1), not a test score.")
    duration_seconds: float
    no_speech: bool


class SynthesizeRequest(RequestModel):
    patient_id: RecordId | None = None
    language: Language
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
