"""Speech recognition and synthesis (Stage 5). Optional: everything has a touch alternative.

Audio is processed in memory and discarded. Transcripts are returned to the caller and
never stored or logged.
"""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import DbSessionDep, PrincipalDep, SettingsDep
from app.core.errors import AppError
from app.models.enums import ConsentType, Language
from app.schemas.common import ErrorResponse
from app.schemas.speech import (
    LanguageSupport,
    ProviderStatusOut,
    SpeechStatus,
    SynthesizeRequest,
    TranscriptionOut,
)
from app.services.access import Permission, authorize, has_consent
from app.speech.audio import decode_wav
from app.speech.base import LanguageUnsupported, SpeechError
from app.speech.registry import asr_provider, tts_provider

router = APIRouter(prefix="/speech", tags=["speech"])
TRANSCRIBE_PATH_SUFFIX = "/speech/transcribe"

_ERRORS = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def _raise(error: SpeechError) -> None:
    details = [{k: v} for k, v in error.details.items()] or None
    raise AppError(error.status, error.code, error.message, details) from error


@router.get("/status", response_model=SpeechStatus, responses=_ERRORS)
def speech_status(_: PrincipalDep, settings: SettingsDep) -> SpeechStatus:
    """Which speech features work right now, per language. Never claims unverified support."""
    asr = asr_provider(settings.asr_model_path, settings.asr_compute_type)
    tts = tts_provider(settings.tts_model_path)
    a, t = asr.status(), tts.status()
    return SpeechStatus(
        asr=ProviderStatusOut(**a.__dict__),
        tts=ProviderStatusOut(**t.__dict__),
        languages=[
            LanguageSupport(
                language=lang,
                speech_recognition=a.available and asr.supports(lang.value),
                speech_synthesis=t.available and tts.supports(lang.value),
            )
            for lang in Language
        ],
    )


@router.post("/transcribe", response_model=TranscriptionOut, responses=_ERRORS)
async def transcribe(
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
    audio: Annotated[UploadFile, File(description="16-bit PCM WAV, mono or stereo, 8–48 kHz")],
    patient_id: Annotated[str, Form()],
    language: Annotated[Language, Form()],
) -> TranscriptionOut:
    access = authorize(db, principal.user, patient_id, Permission.RECORD_ACTIVITY, request=request)
    if not has_consent(db, access.patient.id, ConsentType.VOICE_PROCESSING):
        raise AppError(
            409, "consent_required", "Voice-processing consent is needed before speech can be used."
        )
    data = await audio.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise AppError(413, "file_too_large", "The recording is too large.")
    provider = asr_provider(settings.asr_model_path, settings.asr_compute_type)
    try:
        if not provider.supports(language.value):
            # Check before decoding so unsupported languages fail fast with a clear message.
            raise LanguageUnsupported(
                "Speech recognition is not available for this language.",
                supported=provider.status().languages,
            )
        samples, _ = decode_wav(data, max_seconds=settings.asr_max_audio_seconds)
        result = provider.transcribe(samples, language.value)
    except SpeechError as error:
        _raise(error)
    return TranscriptionOut(**result.__dict__)


@router.post(
    "/synthesize",
    response_class=Response,
    responses={200: {"content": {"audio/wav": {}}}, **_ERRORS},
)
def synthesize(
    body: SynthesizeRequest,
    principal: PrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
    request: Request,
) -> Response:
    if body.patient_id is not None:
        authorize(db, principal.user, body.patient_id, Permission.VIEW_PROFILE, request=request)
    if len(body.text) > settings.tts_max_chars:
        raise AppError(
            422, "text_too_long", f"Text is limited to {settings.tts_max_chars} characters."
        )
    provider = tts_provider(settings.tts_model_path)
    try:
        if not provider.supports(body.language.value):
            raise LanguageUnsupported(
                "A voice is not available for this language.", supported=provider.status().languages
            )
        audio = provider.synthesize(body.text, body.language.value)
    except SpeechError as error:
        _raise(error)
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
