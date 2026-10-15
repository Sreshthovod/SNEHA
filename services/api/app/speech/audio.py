"""Audio validation and decoding (WAV PCM only, standard library + NumPy)."""

import io
import wave

import numpy as np

from app.speech.base import InvalidAudio

TARGET_RATE = 16_000
MIN_SECONDS = 0.3


def decode_wav(data: bytes, *, max_seconds: float) -> tuple[np.ndarray, float]:
    """Return (mono float32 samples at 16 kHz in [-1, 1], duration seconds)."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise InvalidAudio("Audio must be a WAV file (PCM, 16-bit).")
    try:
        with wave.open(io.BytesIO(data)) as wav:
            channels, width, rate, frames = (
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getframerate(),
                wav.getnframes(),
            )
            raw = wav.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise InvalidAudio(f"Could not read the WAV file: {error}") from error

    if width != 2:
        raise InvalidAudio("Only 16-bit PCM WAV audio is supported.")
    if not 8_000 <= rate <= 48_000:
        raise InvalidAudio("Sample rate must be between 8 kHz and 48 kHz.")
    if channels not in (1, 2):
        raise InvalidAudio("Audio must be mono or stereo.")
    duration = frames / rate
    if duration < MIN_SECONDS:
        raise InvalidAudio("The recording is too short.")
    if duration > max_seconds:
        raise InvalidAudio(f"The recording is longer than {max_seconds:.0f} seconds.")

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)
    if float(np.max(np.abs(samples))) < 1e-4:
        raise InvalidAudio("The recording is silent.")
    if rate != TARGET_RATE:
        target_len = int(round(len(samples) * TARGET_RATE / rate))
        positions = np.linspace(0, len(samples) - 1, target_len)
        samples = np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)
    return samples, duration


def encode_wav(samples: np.ndarray, rate: int) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return out.getvalue()
