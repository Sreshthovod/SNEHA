"""Speech provider interfaces and errors.

Providers never fabricate output: if a model is missing, a language is unsupported or
the audio is unusable, they raise a typed error that the API turns into a clear message.
"""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class SpeechError(Exception):
    code = "speech_error"
    status = 500

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ModelMissing(SpeechError):
    code, status = "model_missing", 503


class ProviderUnavailable(SpeechError):
    code, status = "speech_unavailable", 503


class LanguageUnsupported(SpeechError):
    code, status = "language_unsupported", 422


class InvalidAudio(SpeechError):
    code, status = "invalid_audio", 422


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str
    provider: str
    model: str
    confidence: float | None  # mean segment probability, 0..1; None if the model gives none
    duration_seconds: float
    no_speech: bool  # True when the model heard no speech (text is then empty)


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    configured: bool
    available: bool
    model: str | None
    languages: list[str]
    detail: str


class ASRProvider(Protocol):
    name: str

    def status(self) -> ProviderStatus: ...

    def supports(self, language: str) -> bool: ...

    def transcribe(self, samples: np.ndarray, language: str) -> Transcription: ...


class TTSProvider(Protocol):
    name: str

    def status(self) -> ProviderStatus: ...

    def supports(self, language: str) -> bool: ...

    def synthesize(self, text: str, language: str) -> bytes:  # 16-bit PCM WAV
        ...
