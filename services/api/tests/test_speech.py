"""Speech: validation, unsupported languages, missing weights, consent, and — when a model
has been downloaded explicitly — a real transcription of a SYNTHETIC voice recording
(tests/fixtures/synthetic_speech_en.wav, generated with macOS `say`; not a real person)."""

import io
import os
import wave
from pathlib import Path

import numpy as np
import pytest

from app.api.deps import get_settings
from app.speech.audio import decode_wav, encode_wav
from app.speech.base import InvalidAudio, LanguageUnsupported, ModelMissing, Transcription
from app.speech.parler import IndicParlerProvider
from app.speech.registry import asr_provider
from app.speech.whisper import WHISPER_SNEHA_LANGUAGES, FasterWhisperProvider
from tests.helpers import Api

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_speech_en.wav"
REPO_MODEL = Path(__file__).resolve().parents[3] / "models" / "asr" / "faster-whisper-tiny"
MODEL_PATH = Path(os.environ.get("SNEHA_TEST_ASR_MODEL_PATH", REPO_MODEL))
HAVE_MODEL = (MODEL_PATH / "model.bin").is_file()


def wav(seconds=1.0, rate=16000, channels=1, width=2, amplitude=0.3) -> bytes:
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    tone = (amplitude * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    if channels == 2:
        tone = np.repeat(tone, 2)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(tone.tobytes() if width == 2 else (tone // 256).astype("i1").tobytes())
    return out.getvalue()


# ---------------- audio validation ----------------


def test_decode_resamples_and_downmixes() -> None:
    samples, duration = decode_wav(wav(1.0, rate=44100, channels=2), max_seconds=60)
    assert abs(duration - 1.0) < 0.01
    assert abs(len(samples) - 16000) <= 1
    assert samples.dtype == np.float32 and float(np.max(np.abs(samples))) <= 1.0


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not audio at all" * 10, "WAV"),
        (b"", "WAV"),
        (wav(0.1), "too short"),
        (wav(3.0), "longer than"),
        (wav(1.0, width=1), "16-bit"),
        (wav(1.0, rate=4000), "Sample rate"),
        (wav(1.0, amplitude=0.0), "silent"),
        (b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 40, "Could not read"),
    ],
)
def test_invalid_audio_is_rejected(data: bytes, message: str) -> None:
    with pytest.raises(InvalidAudio, match=message):
        decode_wav(data, max_seconds=2)


def test_encode_roundtrip() -> None:
    samples = np.sin(np.linspace(0, 100, 16000)).astype(np.float32) * 0.5
    decoded, _ = decode_wav(encode_wav(samples, 16000), max_seconds=10)
    assert np.allclose(decoded, samples, atol=1e-3)


# ---------------- providers without weights ----------------


def test_whisper_language_coverage_is_the_verified_subset() -> None:
    from faster_whisper.tokenizer import _LANGUAGE_CODES

    assert set(WHISPER_SNEHA_LANGUAGES) <= set(_LANGUAGE_CODES)
    for unsupported in ("brx", "grt", "kha", "lus", "mni", "nag"):
        assert unsupported not in _LANGUAGE_CODES
        assert not FasterWhisperProvider(None).supports(unsupported)


def test_missing_weights_are_reported_not_faked(tmp_path) -> None:
    provider = FasterWhisperProvider(tmp_path / "nothing-here")
    status = provider.status()
    assert status.configured and not status.available
    with pytest.raises(ModelMissing):
        provider.transcribe(np.zeros(16000, dtype=np.float32), "en")
    unconfigured = FasterWhisperProvider(None).status()
    assert not unconfigured.configured and "download_models.py" in unconfigured.detail
    with pytest.raises(LanguageUnsupported):
        provider.transcribe(np.zeros(16000, dtype=np.float32), "kha")


def test_tts_missing_weights_and_unsupported_language(tmp_path) -> None:
    provider = IndicParlerProvider(tmp_path)
    assert not provider.status().available
    with pytest.raises(ModelMissing):
        provider.synthesize("Namaste", "hi")
    with pytest.raises(LanguageUnsupported):
        provider.synthesize("Khublei", "kha")


# ---------------- API ----------------


@pytest.fixture
def speaker(api: Api):
    owner = api.user()
    pid = api.patient(owner)
    api.consent(owner, pid, "voice_processing", "granted")
    device = api.pair_device(owner, pid)
    return owner, pid, device


def post_audio(api, actor, pid, data, language="en"):
    return api.client.post(
        "/api/v1/speech/transcribe",
        data={"patient_id": pid, "language": language},
        files={"audio": ("clip.wav", data, "audio/wav")},
        headers=actor.headers,
    )


def test_status_reports_per_language_support(api: Api, speaker) -> None:
    _, _, device = speaker
    body = api.client.get("/api/v1/speech/status", headers=device.headers).json()
    assert body["asr"]["available"] is False  # no model configured in tests
    by_lang = {row["language"]: row for row in body["languages"]}
    assert by_lang["kha"]["speech_recognition"] is False
    assert "touch alternative" in body["touch_alternative"]


def test_transcribe_without_model_is_503_with_setup_instructions(api: Api, speaker) -> None:
    _, pid, device = speaker
    response = post_audio(api, device, pid, wav(1.0))
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "model_missing"
    assert "download_models.py" in str(error["details"])


def test_unsupported_language_is_422(api: Api, speaker) -> None:
    _, pid, device = speaker
    response = post_audio(api, device, pid, wav(1.0), language="mni")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "language_unsupported"


def test_invalid_audio_via_api(api: Api, speaker, app, tmp_path) -> None:
    _, pid, device = speaker
    (tmp_path / "model.bin").write_bytes(b"fake")  # weights "present" so validation is reached
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"asr_model_path": tmp_path}
    )
    response = post_audio(api, device, pid, b"definitely not a wav file" * 4)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_audio"


def test_consent_and_authorization(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    no_consent = post_audio(api, device, pid, wav(1.0))
    assert no_consent.status_code == 409
    assert no_consent.json()["error"]["code"] == "consent_required"
    outsider = api.user()
    assert post_audio(api, outsider, pid, wav(1.0)).status_code == 404
    assert api.client.get("/api/v1/speech/status").status_code == 401


def test_synthesize_without_model_and_validation(api: Api, speaker) -> None:
    _, pid, device = speaker
    url = "/api/v1/speech/synthesize"
    missing = api.client.post(
        url, json={"language": "as", "text": "Namaskar"}, headers=device.headers
    )
    assert missing.status_code == 503
    unsupported = api.client.post(
        url, json={"language": "lus", "text": "Chibai"}, headers=device.headers
    )
    assert unsupported.status_code == 422
    too_long = api.client.post(
        url, json={"language": "en", "text": "x" * 401}, headers=device.headers
    )
    assert too_long.json()["error"]["code"] == "text_too_long"


def test_fake_provider_success_path_returns_transcript_without_storing(
    api: Api, speaker, monkeypatch, caplog
) -> None:
    _, pid, device = speaker

    class Fake:
        name = "fake"

        def supports(self, language):
            return True

        def status(self):
            raise AssertionError

        def transcribe(self, samples, language):
            return Transcription("synthetic words", language, "fake", "fake-1", 0.9, 1.0, False)

    monkeypatch.setattr("app.api.routes.speech.asr_provider", lambda *a: Fake())
    caplog.set_level("DEBUG")
    response = post_audio(api, device, pid, wav(1.0))
    assert response.status_code == 200
    assert response.json()["text"] == "synthetic words"
    assert "synthetic words" not in caplog.text


# ---------------- real model (only when explicitly downloaded) ----------------


@pytest.mark.skipif(
    not HAVE_MODEL, reason="Run scripts/download_models.py asr --size tiny to enable"
)
def test_real_whisper_transcribes_synthetic_recording(api: Api, speaker, app) -> None:
    asr_provider.cache_clear()
    _, pid, device = speaker
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"asr_model_path": MODEL_PATH}
    )
    response = post_audio(api, device, pid, FIXTURE.read_bytes(), language="en")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "faster_whisper"
    assert body["no_speech"] is False
    words = body["text"].lower()
    assert "tea" in words and "morning" in words
    assert 0 < body["confidence"] <= 1
