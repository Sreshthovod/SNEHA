"""Speech recognition with faster-whisper (CTranslate2 Whisper; MIT licence).

Weights are NEVER downloaded here. Run `scripts/download_models.py asr` once and set
SNEHA_ASR_MODEL_PATH. The model is loaded lazily on the first request, not at startup.

Language coverage was verified against faster_whisper.tokenizer._LANGUAGE_CODES:
Whisper supports as, bn, en, hi, ne of SNEHA's languages, and NOT brx, grt, kha, lus,
mni, nag. Accuracy for Assamese and Nepali is markedly lower than for Hindi/English;
evaluate with native speakers (and older voices) before relying on it.
"""

import logging
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
    importable,
)

logger = logging.getLogger(__name__)

WHISPER_SNEHA_LANGUAGES = ("as", "bn", "en", "hi", "ne")
SETUP_HINT = (
    "Download a model explicitly: `uv run python scripts/download_models.py asr --size small`, "
    "then set SNEHA_ASR_MODEL_PATH to the printed directory."
)


def _importable() -> bool:
    return importable("faster_whisper")


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
        installed = _importable()
        if not configured:
            detail = SETUP_HINT
        elif not present:
            detail = "model files not found"
        elif not installed:
            detail = "faster-whisper is not installed (install the `speech` dependency group)"
        else:
            detail = "ready"
        return ProviderStatus(
            name=self.name,
            configured=configured,
            available=present and installed,
            model=self.model_path.name if self.model_path else None,
            languages=list(WHISPER_SNEHA_LANGUAGES),
            detail=detail,
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
                try:
                    self._model = WhisperModel(
                        str(self.model_path), device=self.device, compute_type=self.compute_type
                    )
                except Exception as error:  # corrupt / incompatible weights
                    # Only the error type is logged; messages can contain file paths.
                    logger.warning("ASR model failed to load: %s", type(error).__name__)
                    raise ProviderUnavailable(
                        "The speech recognition model could not be loaded.", setup=SETUP_HINT
                    ) from None
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
