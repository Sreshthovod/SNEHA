"""Speech recognition with faster-whisper (CTranslate2 Whisper; MIT licence).

Weights are NEVER downloaded here. Run `scripts/download_models.py asr` once and set
SNEHA_ASR_MODEL_PATH. The model is loaded lazily on the first request, not at startup.

Language coverage was verified against faster_whisper.tokenizer._LANGUAGE_CODES:
Whisper supports as, bn, en, hi, ne of SNEHA's languages, and NOT brx, grt, kha, lus,
mni, nag. Accuracy for Assamese and Nepali is markedly lower than for Hindi/English;
evaluate with native speakers (and older voices) before relying on it.
"""

import math
import threading
from pathlib import Path

import numpy as np

from app.speech.base import (
    LanguageUnsupported,
    ModelMissing,
    ProviderStatus,
    ProviderUnavailable,
    Transcription,
)

WHISPER_SNEHA_LANGUAGES = ("as", "bn", "en", "hi", "ne")
SETUP_HINT = (
    "Download a model explicitly: `uv run python scripts/download_models.py asr --size small`, "
    "then set SNEHA_ASR_MODEL_PATH to the printed directory."
)


class FasterWhisperProvider:
    name = "faster_whisper"

    def __init__(
        self, model_path: Path | None, *, compute_type: str = "int8", device: str = "cpu"
    ) -> None:
        self.model_path = model_path
        self.compute_type = compute_type
        self.device = device
        self._model = None
        self._lock = threading.Lock()

    def _weights_present(self) -> bool:
        return bool(self.model_path and (self.model_path / "model.bin").is_file())

    def status(self) -> ProviderStatus:
        configured = self.model_path is not None
        present = self._weights_present()
        return ProviderStatus(
            name=self.name,
            configured=configured,
            available=present,
            model=self.model_path.name if self.model_path else None,
            languages=list(WHISPER_SNEHA_LANGUAGES),
            detail="ready" if present else ("model files not found" if configured else SETUP_HINT),
        )

    def supports(self, language: str) -> bool:
        return language in WHISPER_SNEHA_LANGUAGES

    def _load(self):
        if not self._weights_present():
            raise ModelMissing("The speech recognition model is not installed.", setup=SETUP_HINT)
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as error:  # speech group not installed
                    raise ProviderUnavailable("faster-whisper is not installed.") from error
                self._model = WhisperModel(
                    str(self.model_path), device=self.device, compute_type=self.compute_type
                )
        return self._model

    def transcribe(self, samples: np.ndarray, language: str) -> Transcription:
        if not self.supports(language):
            raise LanguageUnsupported(
                "Speech recognition is not available for this language.",
                supported=list(WHISPER_SNEHA_LANGUAGES),
            )
        model = self._load()
        segments, info = model.transcribe(
            samples,
            language=language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segments = list(segments)
        text = " ".join(s.text.strip() for s in segments).strip()
        probs = [math.exp(s.avg_logprob) for s in segments if s.avg_logprob is not None]
        return Transcription(
            text=text,
            language=language,
            provider=self.name,
            model=self.model_path.name if self.model_path else "unknown",
            confidence=round(sum(probs) / len(probs), 3) if probs else None,
            duration_seconds=round(float(info.duration), 2),
            no_speech=not text,
        )
