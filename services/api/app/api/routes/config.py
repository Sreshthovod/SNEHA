"""What this server can do right now, so clients can show online/offline features honestly."""

from fastapi import APIRouter

from app.api.deps import PrincipalDep, SettingsDep
from app.core.config import ConversationProvider
from app.core.version import service_version
from app.models.enums import Language
from app.schemas.care import REPORT_MAX_DAYS, REPORT_MIN_DAYS
from app.schemas.common import ErrorResponse
from app.schemas.config import ConfigStatus, FeatureStatus
from app.services.files import ALLOWED_UPLOAD_TYPES

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/status", response_model=ConfigStatus, responses={401: {"model": ErrorResponse}})
def config_status(_: PrincipalDep, settings: SettingsDep) -> ConfigStatus:
    gemini_on = (
        settings.conversation_provider is ConversationProvider.GEMINI and settings.gemini_configured
    )
    return ConfigStatus(
        environment=settings.environment.value,
        api_version=service_version(),
        supported_languages=list(Language),
        max_upload_bytes=settings.max_upload_bytes,
        allowed_upload_types=list(ALLOWED_UPLOAD_TYPES),
        report_period_days=[REPORT_MIN_DAYS, REPORT_MAX_DAYS],
        features=[
            FeatureStatus(
                name="conversation_understanding",
                available=True,
                mode=(
                    "gemini"
                    if gemini_on
                    else "local"
                    if settings.conversation_provider is ConversationProvider.LOCAL
                    and settings.local_llm_base_url
                    else "deterministic"
                ),
                detail="POST /conversation/analyze. Gemini is used only with cloud-AI consent; "
                "the deterministic engine is always the fallback.",
            ),
            FeatureStatus(
                name="report_generation",
                available=True,
                mode="pdf",
                detail="8–9 day PDF reports generated from stored activity data.",
            ),
            FeatureStatus(
                name="sync", available=True, mode="push_pull", detail="Explicit device sync."
            ),
            FeatureStatus(
                name="media_storage", available=True, mode="local_disk", detail="Protected files."
            ),
        ],
    )
