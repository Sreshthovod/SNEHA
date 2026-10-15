"""Provider interface and the failure codes that trigger the deterministic fallback."""

from enum import StrEnum
from typing import Protocol

from app.conversation.context import PatientContext
from app.conversation.extraction import ModelExtraction
from app.models.enums import Language


class FailureCode(StrEnum):
    NOT_CONFIGURED = "not_configured"
    NO_CLOUD_CONSENT = "cloud_ai_consent_not_granted"
    TIMEOUT = "timeout"
    NETWORK_UNAVAILABLE = "network_unavailable"
    INVALID_CREDENTIALS = "invalid_credentials"
    QUOTA_EXHAUSTED = "quota_exhausted"
    SAFETY_BLOCKED = "safety_blocked"
    MALFORMED_OUTPUT = "malformed_output"
    SCHEMA_INVALID = "schema_invalid_output"
    EMPTY_OUTPUT = "empty_output"
    PROVIDER_ERROR = "provider_error"


class ProviderFailure(Exception):
    """A provider could not produce a valid extraction. Never carries user text."""

    def __init__(self, code: FailureCode) -> None:
        super().__init__(code.value)
        self.code = code


class ConversationProvider(Protocol):
    name: str

    def analyze(self, text: str, language: Language, context: PatientContext) -> ModelExtraction:
        """Return a schema-valid extraction or raise ProviderFailure."""
        ...
