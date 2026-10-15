"""Application settings loaded from environment variables.

All secrets come from the environment (or a local, git-ignored `.env` file).
Nothing secret is ever hardcoded here; defaults are safe for local development only.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class ConversationProvider(StrEnum):
    """Which engine handles conversation understanding.

    `deterministic` never leaves the server and always works.
    `gemini` is optional and falls back to `deterministic` when unavailable.
    """

    DETERMINISTIC = "deterministic"
    GEMINI = "gemini"
    # Optional OpenAI-compatible model server on your own hardware (llama.cpp, Ollama, vLLM).
    LOCAL = "local"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SNEHA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SNEHA API"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # Development default is a local SQLite file. Deployed environments must use PostgreSQL.
    database_url: str = "sqlite:///./sneha_dev.db"
    database_echo: bool = False

    # Comma-separated in the environment, e.g. "http://localhost:5173,https://dash.example.org".
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # Server-side secret used to HMAC pairing codes. Required outside development/test.
    secret_key: SecretStr | None = None

    # Auth: opaque bearer tokens stored hashed in auth_sessions.
    session_ttl_hours: int = Field(default=12, ge=1, le=24 * 7)
    device_session_ttl_days: int = Field(default=90, ge=1, le=365)
    max_failed_logins: int = Field(default=5, ge=1, le=50)
    lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)
    pairing_code_ttl_minutes: int = Field(default=15, ge=5, le=24 * 60)
    max_clinician_grant_days: int = Field(default=180, ge=1, le=730)

    # Protected file storage (outside any web root).
    media_root: Path = Path("./var/media")
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    # Request body limit for everything except file uploads.
    max_json_body_bytes: int = Field(default=1024 * 1024, ge=1024, le=20 * 1024 * 1024)

    # Version of the privacy notice that consent records refer to.
    consent_policy_version: str = "2026-10"

    # Speech (Stage 5). Paths point to EXPLICITLY downloaded weights; nothing downloads at startup.
    asr_model_path: Path | None = None  # faster-whisper (CTranslate2) model directory
    asr_compute_type: str = "int8"
    asr_max_audio_seconds: float = Field(default=60, ge=5, le=300)
    tts_model_path: Path | None = None  # Indic Parler-TTS model directory
    tts_max_chars: int = Field(default=400, ge=20, le=2000)

    # Optional Unicode TTF (e.g. NotoSans-Regular.ttf) so PDF reports can print Indic
    # scripts. Without it, characters outside Latin-1 are replaced in PDFs.
    report_font_path: Path | None = None

    conversation_provider: ConversationProvider = ConversationProvider.DETERMINISTIC
    gemini_api_key: SecretStr | None = None
    # Verify against `client.models.list()` before deploying; model IDs are retired over time.
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    gemini_max_output_tokens: int = Field(default=1024, ge=128, le=8192)
    # Local model server, e.g. "http://127.0.0.1:11434" (Ollama) or "http://127.0.0.1:8080"
    # (llama.cpp). Only used when SNEHA_CONVERSATION_PROVIDER=local.
    local_llm_base_url: str | None = None
    local_llm_model: str = "llama3.2:3b-instruct"
    local_llm_timeout_seconds: float = Field(default=15.0, gt=0, le=120)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _check_database_scheme(cls, value: str) -> str:
        allowed = ("sqlite://", "postgresql://", "postgresql+psycopg://")
        if not value.startswith(allowed):
            raise ValueError("SNEHA_DATABASE_URL must start with one of: " + ", ".join(allowed))
        # Normalise plain postgresql:// to the psycopg v3 driver we ship with.
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def _check_deployed_requirements(self) -> "Settings":
        if self.environment in (Environment.STAGING, Environment.PRODUCTION):
            problems: list[str] = []
            if self.is_sqlite:
                problems.append("SNEHA_DATABASE_URL must point to PostgreSQL")
            if self.secret_key is None or len(self.secret_key.get_secret_value()) < 32:
                problems.append("SNEHA_SECRET_KEY must be set to at least 32 characters")
            if self.debug:
                problems.append("SNEHA_DEBUG must be false")
            if self.database_echo:
                # Echo logs every statement with its parameters, i.e. patient data.
                problems.append("SNEHA_DATABASE_ECHO must be false")
            if "*" in self.cors_allowed_origins:
                problems.append("SNEHA_CORS_ALLOWED_ORIGINS must not contain '*'")
            elif any(not o.startswith("https://") for o in self.cors_allowed_origins):
                problems.append("SNEHA_CORS_ALLOWED_ORIGINS must all use https://")
            if problems:
                raise ValueError(
                    f"Invalid configuration for environment '{self.environment}': "
                    + "; ".join(problems)
                )
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def pairing_secret(self) -> bytes:
        if self.secret_key is not None:
            return self.secret_key.get_secret_value().encode()
        # Development/test only (production requires SNEHA_SECRET_KEY).
        return b"sneha-development-only-secret"

    @property
    def gemini_configured(self) -> bool:
        return self.gemini_api_key is not None and bool(self.gemini_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
