"""Text-to-speech with AI4Bharat Indic Parler-TTS (Apache-2.0; gated on Hugging Face).

Optional and heavy: requires PyTorch and the `parler-tts` package (not installed by
default) plus explicitly downloaded weights at SNEHA_TTS_MODEL_PATH. A GPU is strongly
recommended; CPU synthesis works but is slow. Loaded lazily, never at startup.

Languages relevant to SNEHA listed on the model card: as, bn, brx, en, hi, mni, ne.
Not covered: grt, kha, lus, nag — the app falls back to on-screen text and the phone's
system voice where available.
"""

import logging
import threading
from pathlib import Path

from app.speech.audio import encode_wav
from app.speech.base import (
    LanguageUnsupported,
    ModelMissing,
    ProviderStatus,
    ProviderUnavailable,
    importable,
)

logger = logging.getLogger(__name__)

PARLER_SNEHA_LANGUAGES = ("as", "bn", "brx", "en", "hi", "mni", "ne")
SETUP_HINT = (
    "Install PyTorch and parler-tts (see docs/ai-models.md), accept the model licence on "
    "Hugging Face, run `uv run python scripts/download_models.py tts`, then set "
    "SNEHA_TTS_MODEL_PATH."
)
# Optional local copy of the description tokenizer (written by download_models.py tts).
DESCRIPTION_TOKENIZER_DIR = "description_tokenizer"
_DESCRIPTION = (
    "A calm, clear, slow speaker with a warm tone, recorded very close up with no background noise."
)


def _importable() -> bool:
    return importable("torch", "parler_tts", "transformers")


class IndicParlerProvider:
    name = "indic_parler"

    def __init__(self, model_path: Path | None) -> None:
        self.model_path = model_path
        self._loaded = None
        self._lock = threading.Lock()

    def _weights_present(self) -> bool:
        return bool(self.model_path and (self.model_path / "config.json").is_file())

    def status(self) -> ProviderStatus:
        present = self._weights_present()
        installed = _importable()
        if not present:
            detail = SETUP_HINT
        elif not installed:
            detail = "PyTorch / parler-tts / transformers are not installed. " + SETUP_HINT
        else:
            detail = "ready"
        return ProviderStatus(
            name=self.name,
            configured=self.model_path is not None,
            available=present and installed,
            model=self.model_path.name if self.model_path else None,
            languages=list(PARLER_SNEHA_LANGUAGES),
            detail=detail,
        )

    def supports(self, language: str) -> bool:
        return language in PARLER_SNEHA_LANGUAGES

    def _load(self):
        if not self._weights_present():
            raise ModelMissing("The text-to-speech model is not installed.", setup=SETUP_HINT)
        with self._lock:
            if self._loaded is None:
                try:
                    import torch
                    from parler_tts import ParlerTTSForConditionalGeneration
                    from transformers import AutoTokenizer
                except ImportError as error:
                    raise ProviderUnavailable(
                        "PyTorch / parler-tts are not installed.", setup=SETUP_HINT
                    ) from error
                device = "cuda:0" if torch.cuda.is_available() else "cpu"
                # local_files_only everywhere: nothing is ever fetched from the Hub here.
                try:
                    model = ParlerTTSForConditionalGeneration.from_pretrained(
                        str(self.model_path), local_files_only=True
                    ).to(device)
                    tokenizer = AutoTokenizer.from_pretrained(
                        str(self.model_path), local_files_only=True
                    )
                except Exception as error:  # corrupt / incompatible weights
                    # Only the error type is logged; messages can contain file paths.
                    logger.warning("TTS model failed to load: %s", type(error).__name__)
                    raise ProviderUnavailable(
                        "The text-to-speech model could not be loaded.", setup=SETUP_HINT
                    ) from None
                local_desc = self.model_path / DESCRIPTION_TOKENIZER_DIR
                try:
                    desc_tokenizer = AutoTokenizer.from_pretrained(
                        str(local_desc)
                        if local_desc.is_dir()
                        else model.config.text_encoder._name_or_path,  # local HF cache only
                        local_files_only=True,
                    )
                except Exception as error:
                    logger.warning("TTS description tokenizer missing: %s", type(error).__name__)
                    raise ModelMissing(
                        "The text-to-speech model is not fully installed.", setup=SETUP_HINT
                    ) from None
                self._loaded = (torch, model, tokenizer, desc_tokenizer, device)
        return self._loaded

    def synthesize(self, text: str, language: str) -> bytes:
        if not self.supports(language):
            raise LanguageUnsupported(
                "A voice is not available for this language.",
                supported=list(PARLER_SNEHA_LANGUAGES),
            )
        torch, model, tokenizer, desc_tokenizer, device = self._load()
        desc = desc_tokenizer(_DESCRIPTION, return_tensors="pt").to(device)
        prompt = tokenizer(text, return_tensors="pt").to(device)
        with torch.no_grad():
            audio = model.generate(
                input_ids=desc.input_ids,
                attention_mask=desc.attention_mask,
                prompt_input_ids=prompt.input_ids,
                prompt_attention_mask=prompt.attention_mask,
            )
        return encode_wav(audio.cpu().numpy().squeeze(), model.config.sampling_rate)
