"""Conversation analysis: providers, fallbacks, guards, safety, privacy, authorization.

All Gemini traffic is faked (no network). Names and memories are synthetic fixtures.
"""

import json
import logging
import os
import socket
import urllib.error
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from sqlalchemy import func, select

from app.api.routes.conversation import get_provider_overrides
from app.conversation.service import ProviderOverrides
from app.core.config import ConversationProvider
from app.models.care import ConversationRecord
from app.models.memories import MemoryItem
from tests.helpers import Api

URL = "/api/v1/conversation/analyze"
SECRET_TEXT = "Synthetic private words 7f3a"


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def fam(api: Api):
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    ranu = api.memory(
        owner,
        pid,
        kind="person",
        title="Synthetic Ranu, my daughter",
        tags=["ranu", "daughter", "tea"],
    )
    garden = api.memory(
        owner, pid, kind="place", title="Synthetic tea garden", tags=["tea", "garden"]
    )
    return SimpleNamespace(owner=owner, pid=pid, device=device, ranu=ranu, garden=garden)


def say(api: Api, actor, pid, text, **extra):
    return api.client.post(
        URL,
        json={"patient_id": pid, "text": text, "language": "en", **extra},
        headers=actor.headers,
    )


class FakeModels:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        result = self.behaviour(kwargs)
        if isinstance(result, Exception):
            raise result
        return result


def response(text=None, finish="STOP", block=None):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
        prompt_feedback=SimpleNamespace(block_reason=block) if block else None,
    )


def extraction(**overrides):
    base = {
        "topic": "family",
        "intents": ["talk_about_person"],
        "people": [],
        "places": [],
        "routines": [],
        "relevant_memory_ids": [],
        "topic_tags": [],
        "fatigue_expressed": False,
        "distress_expressed": False,
        "stop_requested": False,
        "uncertain": False,
        "clarification": "none",
        "memory_candidates": [],
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.fixture
def gemini(app, settings):
    """Switch the app to Gemini with a fake client. Returns the FakeModels to program."""
    settings.conversation_provider = ConversationProvider.GEMINI
    from pydantic import SecretStr

    settings.gemini_api_key = SecretStr("test-key-not-real")
    fake = FakeModels(lambda kw: response(extraction()))
    factory_calls = []

    def factory(api_key, timeout):
        factory_calls.append((api_key, timeout))
        return SimpleNamespace(models=fake)

    app.dependency_overrides[get_provider_overrides] = lambda: ProviderOverrides(
        gemini_client_factory=factory
    )
    fake.factory_calls = factory_calls
    return fake


def grant_cloud(api, fam):
    api.consent(fam.owner, fam.pid, "cloud_ai", "granted")


# ---------------------------------------------------------------- deterministic


def test_deterministic_greeting_and_time(api: Api, fam) -> None:
    r = say(api, fam.device, fam.pid, "Hello! What time is it?")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "deterministic"
    assert body["fallback"] == {"used": False, "reason": None}
    assert "greeting" in body["understanding"]["intents"]
    assert "ask_time" in body["understanding"]["intents"]
    assert body["reply"].startswith("Hello!") and "It is " in body["reply"]


def test_end_to_end_conversation_to_memory_to_recommendation(api: Api, fam) -> None:
    r = say(api, fam.device, fam.pid, "I miss my daughter Ranu. We used to drink tea together.")
    body = r.json()
    people = body["understanding"]["people"]
    ranu = next(p for p in people if p["memory_id"] == fam.ranu["id"])
    assert ranu["status"] == "stored_fact"
    assert [m["id"] for m in body["memories"]][0] == fam.ranu["id"]
    assert "tea" in body["understanding"]["topic_tags"]
    suggestion = body["suggestion"]
    assert suggestion["action"] == "activity"
    assert suggestion["algorithm_version"] and suggestion["reason_codes"]
    assert "Synthetic Ranu, my daughter" in body["reply"]


def test_turns_share_one_metadata_record_without_text(api: Api, fam) -> None:
    first = say(api, fam.device, fam.pid, SECRET_TEXT + " hello").json()
    cid = first["conversation_id"]
    say(api, fam.device, fam.pid, "what day is it", conversation_id=cid)
    api.db.expire_all()
    record = api.db.get(ConversationRecord, cid)
    assert record.turn_count == 2
    assert set(record.intents) >= {"greeting", "ask_date"}
    assert record.provider.value == "deterministic"
    dump = json.dumps([record.intents, record.extra, record.error_code])
    assert "Synthetic private" not in dump


def test_pending_memory_is_never_returned(api: Api, fam) -> None:
    helper = api.user()
    api.add_caregiver(fam.owner, fam.pid, helper)
    pending = api.memory(
        helper, fam.pid, kind="person", title="Synthetic Bijoy cousin", tags=["bijoy"]
    )
    body = say(api, fam.device, fam.pid, "Tell me about Bijoy").json()
    assert pending["id"] not in json.dumps(body)
    assert all(p["memory_id"] != pending["id"] for p in body["understanding"]["people"])


def test_relationship_not_in_stored_data_is_uncertain(api: Api, fam) -> None:
    body = say(api, fam.device, fam.pid, "Where is my son?").json()
    person = body["understanding"]["people"][0]
    assert person == {
        "mention": "my son",
        "status": "uncertain",
        "memory_id": None,
        "relationship_word": None,
    }
    kinds = {u["type"] for u in body["understanding"]["uncertain_interpretations"]}
    assert "person" in kinds and "relationship" in kinds
    assert body["understanding"]["clarification"] == "which_person"
    assert "Who do you mean?" in body["reply"]


def test_routine_question_uses_stored_routines(api: Api, fam) -> None:
    for title, hhmm in [("Synthetic evening walk", "23:58"), ("Synthetic early tea", "00:01")]:
        api.client.post(
            f"/api/v1/patients/{fam.pid}/routines",
            json={"title": title, "local_time": hhmm, "days_of_week": 127},
            headers=fam.owner.headers,
        )
    body = say(api, fam.device, fam.pid, "What should I do now?").json()
    assert "ask_routine" in body["understanding"]["intents"]
    assert (
        "Next: Synthetic evening walk at 23:58." in body["reply"]
        or "nothing else planned" in body["reply"]
    )


def test_memory_candidates_require_approval_and_are_not_saved(api: Api, fam) -> None:
    before = api.db.scalar(select(func.count()).select_from(MemoryItem))
    body = say(api, fam.device, fam.pid, "I remember when we danced at Bihu in the village.").json()
    candidate = body["memory_candidates"][0]
    assert candidate["requires_approval"] is True
    assert "Bihu" in candidate["title"]
    api.db.expire_all()
    assert api.db.scalar(select(func.count()).select_from(MemoryItem)) == before


# ---------------------------------------------------------------- safety


def test_distress_gives_safety_message_and_no_activity(api: Api, fam) -> None:
    body = say(api, fam.device, fam.pid, "I am scared and my chest hurts").json()
    assert body["safety"]["distress_detected"] is True
    assert "112" in body["safety"]["message"]
    assert body["suggestion"] is None
    assert body["reply"] == body["safety"]["message"]


def test_model_cannot_hide_distress(api: Api, fam, gemini) -> None:
    grant_cloud(api, fam)
    gemini.behaviour = lambda kw: response(extraction(topic="small_talk", intents=["other"]))
    body = say(api, fam.device, fam.pid, "Help me, I fell down").json()
    assert body["provider"] == "gemini"
    assert body["safety"]["distress_detected"] is True
    assert body["suggestion"] is None


def test_fatigue_suggests_a_break(api: Api, fam) -> None:
    body = say(api, fam.device, fam.pid, "I'm so tired today").json()
    assert body["understanding"]["fatigue_expressed"] is True
    assert body["suggestion"]["action"] == "break"
    not_tired = say(api, fam.device, fam.pid, "I am not tired, hello").json()
    assert not_tired["understanding"]["fatigue_expressed"] is False


def test_stop_request_is_respected(api: Api, fam) -> None:
    body = say(api, fam.device, fam.pid, "Please stop, that is enough").json()
    assert body["understanding"]["stop_requested"] is True
    assert body["suggestion"]["action"] == "stop"
    assert body["reply"].startswith("All right, we can stop now")


# ---------------------------------------------------------------- gemini


def test_gemini_happy_path_uses_structured_output_and_minimal_context(
    api: Api, fam, gemini, settings
) -> None:
    grant_cloud(api, fam)
    helper = api.user()
    api.add_caregiver(fam.owner, fam.pid, helper)
    pending = api.memory(helper, fam.pid, title="Synthetic unreviewed wedding", tags=["wedding"])
    gemini.behaviour = lambda kw: response(
        extraction(
            people=[{"mention": "Ranu", "memory_id": fam.ranu["id"], "relationship_word": None}],
            relevant_memory_ids=[fam.ranu["id"]],
            topic_tags=["tea"],
        )
    )
    body = say(api, fam.device, fam.pid, "Ranu made tea").json()
    assert body["provider"] == "gemini" and body["fallback"]["used"] is False
    assert body["understanding"]["people"][0]["status"] == "stored_fact"
    call = gemini.calls[0]
    assert call["model"] == settings.gemini_model
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema["title"] == "ModelExtraction"
    prompt = json.loads(call["contents"])
    sent_ids = {m["id"] for m in prompt["context"]["approved_memories"]}
    assert fam.ranu["id"] in sent_ids and pending["id"] not in sent_ids
    assert "description" not in json.dumps(prompt["context"])
    assert gemini.factory_calls[0][1] == settings.gemini_timeout_seconds


def test_no_cloud_consent_means_no_gemini_call(api: Api, fam, gemini) -> None:
    body = say(api, fam.device, fam.pid, "Hello").json()
    assert body["provider"] == "deterministic"
    assert body["fallback"] == {"used": True, "reason": "cloud_ai_consent_not_granted"}
    assert gemini.calls == [] and gemini.factory_calls == []


def test_gemini_not_configured_falls_back(api: Api, fam, gemini, settings) -> None:
    settings.gemini_api_key = None
    grant_cloud(api, fam)
    body = say(api, fam.device, fam.pid, "Hello").json()
    assert body["fallback"] == {"used": True, "reason": "not_configured"}


def _http_response(status):
    return httpx.Response(status, request=httpx.Request("POST", "https://example.invalid"))


@pytest.mark.parametrize(
    ("behaviour", "reason"),
    [
        (lambda kw: response("{not json"), "malformed_output"),
        (lambda kw: response(extraction(diagnosis="severe")), "schema_invalid_output"),
        (lambda kw: response(json.dumps({"topic": "family"})), "schema_invalid_output"),
        (lambda kw: response(""), "empty_output"),
        (lambda kw: response(extraction(), finish="SAFETY"), "safety_blocked"),
        (lambda kw: response(extraction(), block="SAFETY"), "safety_blocked"),
        (lambda kw: httpx.ReadTimeout("timed out"), "timeout"),
        (lambda kw: httpx.ConnectError("offline"), "network_unavailable"),
        (
            lambda kw: genai_errors.ClientError(401, {"error": {"message": "API key not valid"}}),
            "invalid_credentials",
        ),
        (
            lambda kw: genai_errors.ClientError(403, {"error": {"message": "denied"}}),
            "invalid_credentials",
        ),
        (
            lambda kw: genai_errors.ClientError(429, {"error": {"message": "quota"}}),
            "quota_exhausted",
        ),
        (
            lambda kw: genai_errors.ServerError(503, {"error": {"message": "unavailable"}}),
            "provider_error",
        ),
    ],
)
def test_gemini_failures_fall_back_to_deterministic(
    api: Api, fam, gemini, behaviour, reason
) -> None:
    grant_cloud(api, fam)
    gemini.behaviour = behaviour
    r = say(api, fam.device, fam.pid, "Hello, I miss Ranu")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "deterministic"
    assert body["fallback"] == {"used": True, "reason": reason}
    assert any(p["memory_id"] == fam.ranu["id"] for p in body["understanding"]["people"])
    api.db.expire_all()
    record = api.db.get(ConversationRecord, body["conversation_id"])
    assert record.fallback_used and record.error_code == reason


def test_invented_and_foreign_ids_are_dropped(api: Api, fam, gemini) -> None:
    grant_cloud(api, fam)
    stranger = api.user()
    other_pid = api.patient(stranger)
    foreign = api.memory(
        stranger, other_pid, kind="person", title="Synthetic stranger Ranu", tags=["ranu"]
    )
    invented = "11111111-2222-4333-8444-555555555555"
    gemini.behaviour = lambda kw: response(
        extraction(
            people=[
                {"mention": "Ranu", "memory_id": foreign["id"], "relationship_word": None},
                {
                    "mention": "Ranu",
                    "memory_id": fam.garden["id"],
                    "relationship_word": None,
                },  # wrong kind
            ],
            relevant_memory_ids=[invented, foreign["id"], fam.garden["id"]],
            topic_tags=["tea", "made-up-tag"],
        )
    )
    body = say(api, fam.device, fam.pid, "Ranu").json()
    dumped = json.dumps(body)
    assert invented not in dumped and foreign["id"] not in dumped
    assert all(p["memory_id"] is None for p in body["understanding"]["people"])
    assert body["understanding"]["topic_tags"] == ["tea"]
    assert {m["id"] for m in body["memories"]} <= {fam.ranu["id"], fam.garden["id"]}


def test_model_relationship_claims_need_stored_evidence(api: Api, fam, gemini) -> None:
    grant_cloud(api, fam)
    son = api.memory(fam.owner, fam.pid, kind="person", title="Synthetic Tonmoy", tags=["tonmoy"])
    gemini.behaviour = lambda kw: response(
        extraction(
            people=[
                {
                    "mention": "Tonmoy",
                    "memory_id": son["id"],
                    "relationship_word": "son",
                },  # not said
                {
                    "mention": "my daughter",
                    "memory_id": fam.ranu["id"],
                    "relationship_word": "daughter",
                },
            ]
        )
    )
    body = say(api, fam.device, fam.pid, "Tonmoy came with my daughter").json()
    people = {p["mention"]: p for p in body["understanding"]["people"]}
    assert people["Tonmoy"]["relationship_word"] is None
    assert people["my daughter"]["relationship_word"] == "daughter"  # said AND stored
    assert any(
        u["type"] == "relationship" for u in body["understanding"]["uncertain_interpretations"]
    )


def test_ungrounded_mentions_and_diagnostic_text_never_reach_the_response(
    api: Api, fam, gemini
) -> None:
    grant_cloud(api, fam)
    gemini.behaviour = lambda kw: response(
        extraction(
            people=[{"mention": "Auntie Moni", "memory_id": None, "relationship_word": "aunt"}],
            memory_candidates=[
                {
                    "title": "Shows signs of dementia and decline",
                    "kind": "event",
                    "description": None,
                },
                {"title": "zzmarker invented holiday qq", "kind": "event", "description": None},
                {
                    "title": "danced at Bihu in the village",
                    "kind": "event",
                    "description": "cognitive decline noted",
                },
            ],
        )
    )
    r = say(api, fam.device, fam.pid, "We danced at Bihu in the village")
    text = r.text.lower()
    for forbidden in ("dementia", "decline", "cognitive", "zzmarker", "auntie moni"):
        assert forbidden not in text
    body = r.json()
    assert body["understanding"]["people"] == []
    assert [c["title"] for c in body["memory_candidates"]] == ["danced at Bihu in the village"]
    assert body["memory_candidates"][0]["description"] is None
    assert "raw" not in body and "model_output" not in body


def test_local_provider(api: Api, fam, app, settings) -> None:
    settings.conversation_provider = ConversationProvider.LOCAL
    settings.local_llm_base_url = "http://127.0.0.1:9"
    calls = []

    class Resp:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        content = extraction(
            people=[{"mention": "Ranu", "memory_id": fam.ranu["id"], "relationship_word": None}]
        )
        return Resp({"choices": [{"message": {"content": content}}]})

    app.dependency_overrides[get_provider_overrides] = lambda: ProviderOverrides(
        local_opener=opener
    )
    body = say(api, fam.device, fam.pid, "Ranu").json()
    assert body["provider"] == "local" and body["fallback"]["used"] is False
    assert calls[0][0] == "http://127.0.0.1:9/v1/chat/completions"
    api.db.expire_all()
    record = api.db.get(ConversationRecord, body["conversation_id"])
    assert record.provider == "local"  # stored directly since migration 0007

    def offline(request, timeout):
        raise urllib.error.URLError("refused")

    app.dependency_overrides[get_provider_overrides] = lambda: ProviderOverrides(
        local_opener=offline
    )
    body = say(api, fam.device, fam.pid, "Ranu").json()
    assert body["fallback"] == {"used": True, "reason": "network_unavailable"}


# ---------------------------------------------------------------- privacy & access


def test_text_is_never_logged(api: Api, fam, gemini, caplog) -> None:
    grant_cloud(api, fam)
    caplog.set_level(logging.DEBUG)
    gemini.behaviour = lambda kw: httpx.ReadTimeout(f"timeout while sending {kw['contents']}")
    say(api, fam.device, fam.pid, SECRET_TEXT)
    gemini.behaviour = lambda kw: response("{bad " + SECRET_TEXT)
    say(api, fam.device, fam.pid, SECRET_TEXT)
    assert SECRET_TEXT not in caplog.text
    assert "7f3a" not in caplog.text


def test_deterministic_path_needs_no_network(api: Api, fam, monkeypatch) -> None:
    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert say(api, fam.device, fam.pid, "Hello, I miss Ranu").status_code == 200


def test_authorization(api: Api, fam) -> None:
    outsider = api.user()
    assert say(api, outsider, fam.pid, "hello").status_code == 404
    clinician = api.user("clinician")
    api.grant_clinician(fam.owner, fam.pid, clinician)
    assert say(api, clinician, fam.pid, "hello").status_code == 403
    assert (
        api.client.post(
            URL, json={"patient_id": fam.pid, "text": "hi", "language": "en"}
        ).status_code
        == 401
    )
    assert say(api, fam.owner, fam.pid, "hello").status_code == 200  # caregiver may use it too

    other_pid = api.patient(outsider)
    foreign_session = api.session(outsider, other_pid)
    assert say(api, fam.device, fam.pid, "hi", session_id=foreign_session["id"]).status_code == 404
    other_conv = say(api, outsider, other_pid, "hello").json()["conversation_id"]
    clash = say(api, fam.device, fam.pid, "hi", conversation_id=other_conv)
    assert clash.status_code == 409


def test_requires_data_processing_consent(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, consent=False)
    r = say(api, owner, pid, "hello")
    assert r.status_code == 409 and r.json()["error"]["code"] == "consent_required"


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": "x" * 1001},
        {"language": "klingon"},
        {"transcript_store": True},
        {"available_slugs": ["Bad Slug"]},
    ],
)
def test_validation(api: Api, fam, body) -> None:
    payload = {"patient_id": fam.pid, "text": "hello", "language": "en", **body}
    assert api.client.post(URL, json=payload, headers=fam.device.headers).status_code == 422


def test_draft_language_reply_falls_back_safely(api: Api, fam) -> None:
    body = api.client.post(
        URL,
        json={"patient_id": fam.pid, "text": "नमस्ते", "language": "hi"},
        headers=fam.device.headers,
    ).json()
    assert "greeting" in body["understanding"]["intents"]
    assert body["reply"].startswith("नमस्ते")


@pytest.mark.skipif(
    not (os.environ.get("SNEHA_LIVE_GEMINI") == "1" and os.environ.get("SNEHA_GEMINI_API_KEY")),
    reason="Live Gemini test: set SNEHA_LIVE_GEMINI=1 and SNEHA_GEMINI_API_KEY",
)
def test_live_gemini(api: Api, fam, settings) -> None:
    from pydantic import SecretStr

    settings.conversation_provider = ConversationProvider.GEMINI
    settings.gemini_api_key = SecretStr(os.environ["SNEHA_GEMINI_API_KEY"])
    grant_cloud(api, fam)
    body = say(api, fam.device, fam.pid, "I miss my daughter Ranu").json()
    assert body["provider"] == "gemini", body["fallback"]
    assert any(p["memory_id"] == fam.ranu["id"] for p in body["understanding"]["people"])
