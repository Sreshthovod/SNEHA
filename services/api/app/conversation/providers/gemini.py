"""Gemini provider (official `google-genai` SDK, verified against v2.31.0).

API used: `genai.Client(api_key=..., http_options=types.HttpOptions(timeout=<ms>,
retry_options=types.HttpRetryOptions(attempts=1)))` and
`client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(
system_instruction=..., response_mime_type="application/json",
response_json_schema=<ModelExtraction JSON schema>, temperature=0, max_output_tokens=...))`.

The model only ever returns a ModelExtraction; its output is never shown to anyone
directly. Any error becomes a ProviderFailure with a code, never with user text.
"""

import json
import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.conversation.context import PatientContext
from app.conversation.extraction import ModelExtraction
from app.conversation.providers.base import FailureCode, ProviderFailure
from app.models.enums import Language

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You help an assistive app understand what an older adult said.
Return ONLY JSON matching the given schema. Rules:
- Use ONLY the provided approved memories and routines. Refer to them by their exact id.
  Never invent ids, people, places, relationships or events.
- `mention` fields must copy the person's own words exactly.
- Set `relationship_word` only if the person themselves said it (e.g. "my daughter").
- Set fatigue/distress/stop flags only when explicitly expressed.
- If unsure who or what is meant, set uncertain=true and choose a clarification.
- memory_candidates: only things the person clearly shared in this message; they will be
  reviewed by family before anything is saved.
- Never give medical advice, never diagnose, never comment on memory or cognition.
- topic_tags: choose only from known_tags."""

_BLOCKED_FINISH = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}


def _classify(error: Exception) -> FailureCode:
    from google.genai import errors

    if isinstance(error, errors.ClientError):
        code = getattr(error, "code", None)
        if code in (401, 403):
            return FailureCode.INVALID_CREDENTIALS
        if code == 429:
            return FailureCode.QUOTA_EXHAUSTED
        return FailureCode.PROVIDER_ERROR
    if isinstance(error, errors.APIError):
        return FailureCode.PROVIDER_ERROR
    name = type(error).__name__.lower()
    if isinstance(error, TimeoutError) or "timeout" in name:
        return FailureCode.TIMEOUT
    if isinstance(error, ConnectionError | OSError) or "connect" in name or "network" in name:
        return FailureCode.NETWORK_UNAVAILABLE
    return FailureCode.PROVIDER_ERROR


def parse_extraction(raw: str | None) -> ModelExtraction:
    if not raw or not raw.strip():
        raise ProviderFailure(FailureCode.EMPTY_OUTPUT)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProviderFailure(FailureCode.MALFORMED_OUTPUT) from error
    try:
        return ModelExtraction.model_validate(data)
    except ValidationError as error:
        raise ProviderFailure(FailureCode.SCHEMA_INVALID) from error


def build_prompt(text: str, language: Language, context: PatientContext) -> str:
    return json.dumps(
        {"language": language.value, "context": context.for_prompt(), "message": text},
        ensure_ascii=False,
    )


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        client_factory: Callable[[str, float], Any] | None = None,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._timeout = timeout_seconds
        self._api_key = api_key
        self._factory = client_factory or _default_client

    def analyze(self, text: str, language: Language, context: PatientContext) -> ModelExtraction:
        from google.genai import types

        try:
            client = self._factory(self._api_key, self._timeout)
            response = client.models.generate_content(
                model=self.model,
                contents=build_prompt(text, language, context),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_json_schema=ModelExtraction.model_json_schema(),
                    temperature=0,
                    max_output_tokens=self.max_output_tokens,
                ),
            )
        except ProviderFailure:
            raise
        except Exception as error:
            code = _classify(error)
            # Log the failure class only: exception messages may echo request content.
            logger.warning("Gemini request failed: %s (%s)", code.value, type(error).__name__)
            raise ProviderFailure(code) from None

        if getattr(response, "prompt_feedback", None) is not None and getattr(
            response.prompt_feedback, "block_reason", None
        ):
            raise ProviderFailure(FailureCode.SAFETY_BLOCKED)
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            reason = getattr(candidates[0], "finish_reason", None)
            reason_name = getattr(reason, "name", str(reason) if reason else "")
            if reason_name in _BLOCKED_FINISH:
                raise ProviderFailure(FailureCode.SAFETY_BLOCKED)
        try:
            raw = response.text
        except Exception:  # SDK raises when there is no text part
            raise ProviderFailure(FailureCode.EMPTY_OUTPUT) from None
        return parse_extraction(raw)


def _default_client(api_key: str, timeout_seconds: float) -> Any:
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=int(timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),  # no retries in the user's path
        ),
    )
