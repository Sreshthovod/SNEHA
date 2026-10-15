"""Provider construction from settings (cached per settings object)."""

from functools import lru_cache
from pathlib import Path

from app.speech.parler import IndicParlerProvider
from app.speech.whisper import FasterWhisperProvider


@lru_cache(maxsize=4)
def asr_provider(model_path: Path | None, compute_type: str) -> FasterWhisperProvider:
    return FasterWhisperProvider(model_path, compute_type=compute_type)


@lru_cache(maxsize=4)
def tts_provider(model_path: Path | None) -> IndicParlerProvider:
    return IndicParlerProvider(model_path)
