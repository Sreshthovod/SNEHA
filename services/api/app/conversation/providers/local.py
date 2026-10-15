"""Optional local model provider: an OpenAI-compatible chat endpoint on your own hardware.

Disabled unless SNEHA_CONVERSATION_PROVIDER=local and SNEHA_LOCAL_LLM_BASE_URL are set.
Works with llama.cpp `llama-server`, Ollama (`/v1/chat/completions`) or vLLM.

Hardware guidance (verify for your model): a 3B-parameter instruct model quantised to
4 bits needs roughly 3 GB of RAM and answers in a few seconds on a modern 8-core CPU;
7–8B models need ~6–8 GB RAM, and a GPU for interactive speed. The server must not be
exposed to the internet. Text stays on your infrastructure, so cloud-AI consent is not
required, but data-processing consent still is.
"""

import json
import logging
import urllib.error
import urllib.request

from app.conversation.context import PatientContext
from app.conversation.extraction import ModelExtraction
from app.conversation.providers.base import FailureCode, ProviderFailure
from app.conversation.providers.gemini import SYSTEM_INSTRUCTION, build_prompt, parse_extraction
from app.models.enums import Language

logger = logging.getLogger(__name__)


class LocalModelProvider:
    name = "local"

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float, opener=None) -> None:
        self.url = base_url.rstrip("/") + "/v1/chat/completions"
        self.model = model
        self.timeout = timeout_seconds
        self._open = opener or urllib.request.urlopen

    def analyze(self, text: str, language: Language, context: PatientContext) -> ModelExtraction:
        schema = json.dumps(ModelExtraction.model_json_schema())
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION + "\nJSON schema:\n" + schema},
                {"role": "user", "content": build_prompt(text, language, context)},
            ],
        }
        request = urllib.request.Request(  # noqa: S310 - URL comes from operator config
            self.url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except TimeoutError:
            raise ProviderFailure(FailureCode.TIMEOUT) from None
        except urllib.error.HTTPError as error:
            code = FailureCode.QUOTA_EXHAUSTED if error.code == 429 else FailureCode.PROVIDER_ERROR
            raise ProviderFailure(code) from None
        except (urllib.error.URLError, OSError):
            raise ProviderFailure(FailureCode.NETWORK_UNAVAILABLE) from None
        except json.JSONDecodeError:
            raise ProviderFailure(FailureCode.MALFORMED_OUTPUT) from None
        try:
            raw = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderFailure(FailureCode.MALFORMED_OUTPUT) from None
        return parse_extraction(raw)
