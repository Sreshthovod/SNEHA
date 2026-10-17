"""Repeatable demonstration of the corrected SNEHA workflow, on SYNTHETIC data only.

Runs the real API in-process against a fresh, migrated, throwaway SQLite database and
walks one fictional family through the original problem's acceptance criteria. Every
check prints PASS or FAIL with the evidence it used, and the script exits non-zero if
any check fails. Nothing touches your development database or the network.

    cd services/api && uv run python scripts/demo_alignment.py

Phone-only criteria (offline play, the in-activity policy, the caregiver button on the
phone) are demonstrated by Flutter tests; `scripts/demo_alignment.sh` runs both.
"""

import json
import sys
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from alembic import command  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import SecretStr  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.api.routes.conversation import get_provider_overrides  # noqa: E402
from app.conversation.service import ProviderOverrides  # noqa: E402
from app.core.config import ConversationProvider, Environment, Settings, get_settings  # noqa: E402
from app.db.migrations import alembic_config  # noqa: E402
from app.db.session import build_engine, get_db, get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.users import User  # noqa: E402

TZ = ZoneInfo("Asia/Kolkata")
PAIRS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001"  # seeded "picture-pairs"
PASSWORD = "synthetic-demo-password-1"  # noqa: S105 - throwaway demo account
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def uid() -> str:
    return str(uuid.uuid4())


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


@dataclass
class Check:
    criterion: str
    passed: bool
    evidence: str


class Demo:
    def __init__(self, client: TestClient, db: Session, settings: Settings, app) -> None:
        self.c = client
        self.db = db
        self.settings = settings
        self.app = app
        self.checks: list[Check] = []

    # ----- small helpers -----

    def check(self, criterion: str, passed: bool, evidence: str) -> None:
        self.checks.append(Check(criterion, bool(passed), evidence))
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {criterion}\n       {evidence}")

    def user(self, role: str, name: str):
        email = f"synthetic.demo.{role}.{uid()[:8]}@example.org"
        r = self.c.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD, "full_name": name, "role": role},
        )
        r.raise_for_status()
        if role == "clinician":
            user = self.db.get(User, r.json()["id"])
            user.is_verified = True  # an administrator verifies clinicians
            self.db.commit()
        token = self.c.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        ).json()["access_token"]
        return SimpleNamespace(
            id=r.json()["id"], email=email, h={"Authorization": f"Bearer {token}"}
        )

    def push(self, device, *mutations) -> list[str]:
        r = self.c.post(
            "/api/v1/sync/push",
            json={"device_install_id": self.install_id, "mutations": list(mutations)},
            headers=device.h,
        )
        r.raise_for_status()
        return [x["status"] for x in r.json()["results"]]

    @staticmethod
    def mutation(entity: str, data: dict) -> dict:
        return {"mutation_id": uid(), "entity_type": entity, "data": data}

    # ----- the story -----

    def run(self) -> bool:
        print("SNEHA alignment demonstration · SYNTHETIC data only · throwaway database\n")
        today = datetime.now(TZ).date()
        self.period_end = today - timedelta(days=1)
        self.period_start = self.period_end - timedelta(days=8)  # 9 days
        self.install_id = uid()

        self.family()
        self.memory_bank()
        self.sessions_and_events()
        self.adaptation()
        self.fatigue()
        self.stop_and_ai_fallbacks()
        self.trends_review_and_report()
        self.isolation()

        passed = sum(c.passed for c in self.checks)
        print(f"\n{passed} of {len(self.checks)} checks passed.")
        print(
            "Phone-only criteria (offline play, in-activity policy, caregiver button, sync "
            "without network) are covered by Flutter tests in apps/patient_app/test/adaptation "
            "and test/offline; run scripts/demo_alignment.sh for both."
        )
        return passed == len(self.checks)

    def family(self) -> None:
        self.owner = self.user("caregiver", "Synthetic Demo Daughter")
        r = self.c.post(
            "/api/v1/patients",
            json={
                "display_name": "Synthetic Demo Grandmother",
                "preferred_language": "as",
                "relationship_label": "daughter",
                "timezone": "Asia/Kolkata",
            },
            headers=self.owner.h,
        )
        r.raise_for_status()
        self.pid = r.json()["id"]
        self.base = f"/api/v1/patients/{self.pid}"
        self.c.post(
            f"{self.base}/consents",
            json={"consent_type": "data_processing", "status": "granted", "given_by": "patient"},
            headers=self.owner.h,
        ).raise_for_status()
        code = self.c.post(f"{self.base}/pairing-codes", headers=self.owner.h).json()["code"]
        paired = self.c.post(
            "/api/v1/auth/device/pair", json={"code": code, "device_name": "Synthetic phone"}
        ).json()
        self.device = SimpleNamespace(h={"Authorization": f"Bearer {paired['access_token']}"})

    def memory_bank(self) -> None:
        self.c.put(
            f"{self.base}/preferences",
            json={"interests": ["tea", "family"], "disliked_activity_slugs": []},
            headers=self.owner.h,
        ).raise_for_status()
        approved = []
        for title, tags in [
            ("Synthetic Mina, granddaughter", ["family", "mina"]),
            ("Synthetic tea garden at Jorhat", ["tea", "garden"]),
            ("Synthetic Bihu festival", ["festival"]),
            ("Synthetic old village house", ["home"]),
        ]:
            photo = self.c.post(
                f"{self.base}/media",
                files={"file": ("synthetic.png", PNG, "image/png")},
                headers=self.owner.h,
            ).json()
            m = self.c.post(
                f"{self.base}/memories",
                json={
                    "kind": "person" if "Mina" in title else "place",
                    "title": title,
                    "tags": tags,
                    "media_file_id": photo["id"],
                },
                headers=self.owner.h,
            ).json()
            approved.append(m)
        helper = self.user("caregiver", "Synthetic Demo Neighbour")
        self.c.post(
            f"{self.base}/caregivers",
            json={"email": helper.email, "relationship_label": "neighbour", "can_manage": False},
            headers=self.owner.h,
        ).raise_for_status()
        pending = self.c.post(
            f"{self.base}/memories",
            json={"kind": "person", "title": "Synthetic unverified cousin", "tags": ["tea"]},
            headers=helper.h,
        ).json()
        self.helper = helper

        rec = self.c.post(
            "/api/v1/activities/next",
            json={"patient_id": self.pid, "available_slugs": ["photo-recall"]},
            headers=self.device.h,
        ).json()
        refs = rec["content_refs"].get("memory_item_ids", [])
        tea = approved[1]["id"]
        self.check(
            "An approved memory influences a relevant activity",
            rec["activity_slug"] == "photo-recall"
            and tea in refs
            and refs.index(tea) == 0
            and "APPROVED_MEMORIES_USED" in rec["reason_codes"],
            f"photo-recall chosen with memory refs {len(refs)}; the 'tea' memory (approved "
            f"interest 'tea') is first; reasons include APPROVED_MEMORIES_USED",
        )
        pulled = self.c.get("/api/v1/sync/pull?since=0", headers=self.device.h).json()
        ids = {
            c["entity_id"]
            for c in pulled["changes"]
            if c["entity_type"] == "memory_item" and c["operation"] == "upsert"
        }
        self.check(
            "Only approved memories reach the phone or activities",
            pending["status"] == "pending_approval"
            and pending["id"] not in refs
            and pending["id"] not in ids
            and {m["id"] for m in approved} <= ids,
            "the neighbour's proposal is pending_approval: absent from the recommendation "
            f"and from sync; {len(ids)} approved memories synced",
        )

    def sessions_and_events(self) -> None:
        """A week of play recorded offline on the phone, then synced (with a replay)."""
        mutations = []
        # Usual pattern before the period: comfortable results.
        for d in range(14, 8, -1):
            day = self.period_start - timedelta(days=d)
            for hour in (10, 16):
                mutations += self._session(day, hour, score=0.9, rt=2000, hints=0)
        # The period: lower scores and slower answers on most days; days 5 and 9 missing.
        for i in range(9):
            if i in (4, 8):
                continue
            day = self.period_start + timedelta(days=i)
            mutations += self._session(day, 10, score=0.55, rt=3300, hints=1)
        self.event_session = mutations[-2]["data"]["id"]  # the last session pushed
        events = self._events(self.event_session, self.period_start + timedelta(days=7))
        mutations += events
        first = []
        for i in range(0, len(mutations), 200):
            first += self.push(self.device, *mutations[i : i + 200])
        replay = []
        for i in range(0, len(mutations), 200):
            replay += self.push(self.device, *mutations[i : i + 200])
        renamed = [{**m, "mutation_id": uid()} for m in events]
        again = self.push(self.device, *renamed)
        stored = self.c.get(
            f"{self.base}/sessions/{self.event_session}/events", headers=self.owner.h
        ).json()
        self.check(
            "Session events are persisted, not only held in screen state",
            len(stored) == len(events)
            and stored[3]["data"]
            == {"action": "show_hint", "reason_codes": ["REPEATED_ERRORS_IN_ROUND"]},
            f"{len(stored)} events stored server-side for one session, in order "
            f"({', '.join(e['event_type'] for e in stored[:5])}, …)",
        )
        self.check(
            "Synchronisation does not silently duplicate or lose events",
            set(first) == {"applied"}
            and set(replay) == {"duplicate"}
            and set(again) == {"duplicate"}
            and len(stored) == len(events),
            f"{len(first)} mutations applied; replay → all duplicate; the same events under new "
            "mutation IDs → duplicate; an event for an unknown session is rejected (tested)",
        )

    def _session(self, day: date, hour: int, *, score: float, rt: int, hints: int) -> list[dict]:
        sid = uid()
        start = at(day, hour)
        return [
            self.mutation(
                "activity_session",
                {
                    "id": sid,
                    "started_at": iso(start),
                    "ended_at": iso(start + timedelta(minutes=6)),
                    "status": "completed",
                    "end_reason": "completed",
                },
            ),
            self.mutation(
                "activity_result",
                {
                    "id": uid(),
                    "session_id": sid,
                    "activity_id": PAIRS,
                    "difficulty_level": 2,
                    "started_at": iso(start + timedelta(minutes=1)),
                    "completed_at": iso(start + timedelta(minutes=5)),
                    "score": score,
                    "correct_count": 4,
                    "attempt_count": 6,
                    "hint_count": hints,
                    "duration_ms": 240_000,
                    "abandoned": False,
                    "metrics": {"mean_response_ms": rt},
                },
            ),
        ]

    def _events(self, sid: str, day: date) -> list[dict]:
        t = at(day, 10, 1)
        steps = [
            ("activity_started", None, {"rounds_planned": 4, "difficulty": 2}),
            ("attempt", 0, {"correct": False, "latency_ms": 4200}),
            ("attempt", 0, {"correct": False, "latency_ms": 5100}),
            (
                "adaptation",
                0,
                {"action": "show_hint", "reason_codes": ["REPEATED_ERRORS_IN_ROUND"]},
            ),
            ("hint_auto", 0, {"hint_number": 1, "source": "system"}),
            ("attempt", 0, {"correct": True, "latency_ms": 3000}),
            ("round_solved", 0, {}),
            ("activity_ended", None, {"outcome": "completed"}),
        ]
        return [
            self.mutation(
                "activity_event",
                {
                    "id": uid(),
                    "session_id": sid,
                    "activity_id": PAIRS,
                    "seq": i,
                    "event_type": kind,
                    "occurred_at": iso(t + timedelta(seconds=10 * i)),
                    "round_index": rnd,
                    "data": data,
                },
            )
            for i, (kind, rnd, data) in enumerate(steps)
        ]

    def adaptation(self) -> None:
        """Different observed interactions → different, explained decisions."""
        slugs = ["picture-pairs"]
        decisions = {}
        # Sized so the latest result is the one that changes the level (personalization.toml):
        # up after 3 comfortable successes; down after 2 struggles, but never within 3 results
        # of the previous change, so the struggling person first climbs a level.
        for label, scores in [
            ("struggling", [1.0, 1.0, 1.0, 0.2, 0.2, 0.2]),
            ("comfortable", [1.0, 1.0, 1.0]),
        ]:
            fresh = self._fresh_device_patient()
            for i, score in enumerate(scores):
                start = datetime.now(UTC) - timedelta(hours=10 - i)
                self.push(fresh.device, *self._session_at(start, score))
            decisions[label] = self.c.post(
                "/api/v1/activities/next",
                json={"patient_id": fresh.pid, "available_slugs": slugs},
                headers=fresh.device.h,
            ).json()
        s, c = decisions["struggling"], decisions["comfortable"]
        self.check(
            "Different interactions lead to different justified adaptation decisions",
            s["difficulty"] < c["difficulty"]
            and "DIFFICULTY_DECREASED_AFTER_REPEATED_ERRORS" in s["reason_codes"]
            and s["hints_enabled"]
            and "DIFFICULTY_INCREASED_AFTER_COMFORTABLE_SUCCESS" in c["reason_codes"],
            f"after repeated low scores → level {s['difficulty']}, hints on "
            f"({', '.join(r for r in s['reason_codes'] if 'DIFF' in r or 'HINT' in r)}); "
            f"comfortable successes → level {c['difficulty']} "
            f"({', '.join(r for r in c['reason_codes'] if 'DIFF' in r)}). In-activity "
            "decisions (hint, shorten, rest) are the phone policy: Flutter tests",
        )

    def _session_at(self, start: datetime, score: float) -> list[dict]:
        sid = uid()
        return [
            self.mutation(
                "activity_session",
                {
                    "id": sid,
                    "started_at": iso(start),
                    "ended_at": iso(start + timedelta(minutes=5)),
                    "status": "completed",
                    "end_reason": "completed",
                },
            ),
            self.mutation(
                "activity_result",
                {
                    "id": uid(),
                    "session_id": sid,
                    "activity_id": PAIRS,
                    "difficulty_level": 3,
                    "started_at": iso(start),
                    "completed_at": iso(start + timedelta(minutes=4)),
                    "score": score,
                    "correct_count": 3,
                    "attempt_count": 4,
                    "hint_count": 0,
                    "duration_ms": 200_000,
                    "abandoned": False,
                    "metrics": {"mean_response_ms": 2000},
                },
            ),
        ]

    def _fresh_device_patient(self):
        owner = self.user("caregiver", "Synthetic Demo Second Family")
        pid = self.c.post(
            "/api/v1/patients",
            json={
                "display_name": "Synthetic Demo Patient B",
                "preferred_language": "en",
                "relationship_label": "son",
            },
            headers=owner.h,
        ).json()["id"]
        self.c.post(
            f"/api/v1/patients/{pid}/consents",
            json={"consent_type": "data_processing", "status": "granted", "given_by": "patient"},
            headers=owner.h,
        )
        code = self.c.post(f"/api/v1/patients/{pid}/pairing-codes", headers=owner.h).json()["code"]
        token = self.c.post(
            "/api/v1/auth/device/pair", json={"code": code, "device_name": "Synthetic phone B"}
        ).json()["access_token"]
        return SimpleNamespace(
            pid=pid, device=SimpleNamespace(h={"Authorization": f"Bearer {token}"})
        )

    def fatigue(self) -> None:
        before = self.c.post(
            "/api/v1/activities/next", json={"patient_id": self.pid}, headers=self.device.h
        ).json()
        self.c.post(
            f"{self.base}/observations",
            json={
                "observed_at": iso(datetime.now(UTC) - timedelta(minutes=2)),
                "category": "fatigue",
                "fatigue_level": "mild",
                "note": "Synthetic: yawning after lunch",
            },
            headers=self.owner.h,
        ).raise_for_status()
        mild = self.c.post(
            "/api/v1/activities/next", json={"patient_id": self.pid}, headers=self.device.h
        ).json()
        report = self.mutation(
            "fatigue_report",
            {"id": uid(), "level": "severe", "reported_at": iso(datetime.now(UTC))},
        )
        pushed = self.push(self.device, report)
        severe = self.c.post(
            "/api/v1/activities/next", json={"patient_id": self.pid}, headers=self.device.h
        ).json()
        pulled = self.c.get("/api/v1/sync/pull?since=0", headers=self.device.h).json()["changes"]
        to_phone = [c["data"] for c in pulled if c["entity_type"] == "fatigue_report"]
        self.check(
            "Caregiver fatigue input immediately lowers demand or stops activity",
            mild["difficulty"] == 1
            and "LOW_EFFORT_FOR_FATIGUE" in mild["reason_codes"]
            and pushed == ["applied"]
            and severe["action"] == "break"
            and "CAREGIVER_REPORTED_SEVERE_FATIGUE" in severe["reason_codes"]
            and all("note" not in d for d in to_phone)
            and {d["level"] for d in to_phone} == {"mild", "severe"},
            f"before: {before['action']} at level {before['difficulty']}; 'a little tired' → "
            f"{mild['activity_slug']} at level {mild['difficulty']}; 'very tired' from the phone → "
            f"{severe['action']} ({severe['break_minutes']} min). The phone receives level and "
            "time only, and a running activity ends at once (Flutter tests)",
        )

    def stop_and_ai_fallbacks(self) -> None:
        stop = self.c.post(
            "/api/v1/activities/next",
            json={"patient_id": self.pid, "stop_requested": True},
            headers=self.device.h,
        ).json()
        # A (fake) cloud model that says there is no stop request and tries to keep going.
        self.settings.conversation_provider = ConversationProvider.GEMINI
        self.settings.gemini_api_key = SecretStr("synthetic-not-a-real-key")
        self.c.post(
            f"{self.base}/consents",
            json={"consent_type": "cloud_ai", "status": "granted", "given_by": "patient"},
            headers=self.owner.h,
        )
        model_output = json.dumps(
            {
                "topic": "small_talk",
                "intents": ["other"],
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
        )

        class FakeModels:
            def generate_content(self, **_):
                return SimpleNamespace(
                    text=model_output,
                    candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
                    prompt_feedback=None,
                )

        self.app.dependency_overrides[get_provider_overrides] = lambda: ProviderOverrides(
            gemini_client_factory=lambda api_key, timeout: SimpleNamespace(models=FakeModels())
        )
        talk = self.c.post(
            "/api/v1/conversation/analyze",
            json={
                "patient_id": self.pid,
                "text": "No, stop. I don't want to do this.",
                "language": "en",
            },
            headers=self.device.h,
        ).json()

        class Broken:
            def generate_content(self, **_):
                return SimpleNamespace(text="{not json", candidates=[], prompt_feedback=None)

        self.app.dependency_overrides[get_provider_overrides] = lambda: ProviderOverrides(
            gemini_client_factory=lambda api_key, timeout: SimpleNamespace(models=Broken())
        )
        broken = self.c.post(
            "/api/v1/conversation/analyze",
            json={"patient_id": self.pid, "text": "Good morning", "language": "en"},
            headers=self.device.h,
        ).json()
        self.app.dependency_overrides.pop(get_provider_overrides, None)
        self.settings.conversation_provider = ConversationProvider.DETERMINISTIC
        self.check(
            "A stop request cannot be overridden by an AI response",
            stop["action"] == "stop"
            and stop["reason_codes"][0] == "STOP_REQUESTED"
            and talk["provider"] == "gemini"
            and talk["understanding"]["stop_requested"] is True
            and talk["suggestion"]["action"] == "stop",
            "engine: stop first; a model that answered stop_requested=false is overruled "
            f"(provider {talk['provider']}, suggestion {talk['suggestion']['action']})",
        )

        def transcribe(language: str):
            return self.c.post(
                "/api/v1/speech/transcribe",
                data={"patient_id": self.pid, "language": language},
                files={"audio": ("synthetic.wav", _tone_wav(), "audio/wav")},
                headers=self.device.h,
            )

        no_consent = transcribe("as")
        self.c.post(
            f"{self.base}/consents",
            json={"consent_type": "voice_processing", "status": "granted", "given_by": "patient"},
            headers=self.owner.h,
        )
        voice = transcribe("as")
        khasi = transcribe("kha")
        self.check(
            "AI and speech failures produce safe, understandable fallbacks",
            broken["provider"] == "deterministic"
            and broken["fallback"]["used"] is True
            and broken["reply"]
            and no_consent.status_code == 409
            and voice.status_code == 503
            and voice.json()["error"]["code"] == "model_missing"
            and khasi.status_code == 422
            and khasi.json()["error"]["code"] == "language_unsupported",
            f"malformed model output → deterministic reply ({broken['fallback']['reason']}); "
            f"speech: no consent → {no_consent.json()['error']['code']}, no model installed → "
            f"{voice.json()['error']['code']}, Khasi → {khasi.json()['error']['code']} "
            "(never a made-up transcript); the phone keeps large on-screen choices",
        )

    def trends_review_and_report(self) -> None:
        s, e = str(self.period_start), str(self.period_end)
        analytics = self.c.get(
            f"{self.base}/analytics?from={s}&to={e}", headers=self.owner.h
        ).json()
        self.check(
            "Dashboard trends come from stored session records",
            analytics["totals"]["results"] == 7
            and analytics["completeness"]["days_with_activity"] == 7
            and len(analytics["completeness"]["missing_days"]) == 2
            and analytics["baseline"]["status"] == "compared",
            f"7 synced results on 7 of 9 days; missing days "
            f"{analytics['completeness']['missing_days']} are shown as missing, not as low "
            f"scores; usual pattern compared ({analytics['baseline']['results']} earlier results)",
        )
        clinician = self.user("clinician", "Synthetic Demo Clinician")
        self.c.post(
            f"{self.base}/consents",
            json={"consent_type": "clinician_sharing", "status": "granted", "given_by": "patient"},
            headers=self.owner.h,
        )
        self.c.post(
            f"{self.base}/clinician-grants",
            json={
                "clinician_email": clinician.email,
                "expires_at": iso(datetime.now(UTC) + timedelta(days=30)),
                "purpose": "Synthetic memory clinic visit",
            },
            headers=self.owner.h,
        ).raise_for_status()
        items = self.c.post(
            f"{self.base}/review-items/scan",
            json={"period_start": s, "period_end": e},
            headers=self.owner.h,
        ).json()
        change = next(i for i in items if i["kind"] == "change")
        seen_before = self.c.get(f"{self.base}/review-items", headers=clinician.h).json()
        clin_analytics = self.c.get(
            f"{self.base}/analytics?from={s}&to={e}", headers=clinician.h
        ).json()
        no_reason = self.c.post(
            f"{self.base}/review-items/{change['id']}/decision",
            json={"decision": "confirmed"},
            headers=self.owner.h,
        )
        helper_try = self.c.post(
            f"{self.base}/review-items/{change['id']}/decision",
            json={"decision": "confirmed", "reason": "Synthetic"},
            headers=self.helper.h,
        )
        confirmed = self.c.post(
            f"{self.base}/review-items/{change['id']}/decision",
            json={"decision": "confirmed", "reason": "Synthetic: also repeating questions at home"},
            headers=self.owner.h,
        ).json()
        seen_after = self.c.get(f"{self.base}/review-items", headers=clinician.h).json()
        wording = " ".join(i["wording"] + i["explanation"] for i in items).lower()
        self.check(
            "A possible concern requires human review and is never a diagnosis",
            seen_before == []
            and clin_analytics["review_flags"] == []
            and clin_analytics["review_flags_withheld"] is True
            and no_reason.status_code == 422
            and helper_try.status_code == 403
            and confirmed["status"] == "confirmed"
            and [i["id"] for i in seen_after] == [change["id"]]
            and "not a diagnosis" in wording
            and not any(w in wording for w in ("dementia", "decline", "impairment")),
            f"{len(items)} automated prompt(s) ({', '.join(i['rule_id'] for i in items)}) "
            "awaiting review; clinician saw none; a decision needs a managing caregiver and a "
            f"reason; after confirmation the clinician sees exactly 1 ({change['rule_id']})",
        )

        report = self.c.post(
            f"{self.base}/reports", json={"period_start": s, "period_end": e}, headers=self.owner.h
        ).json()
        local = lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(TZ)  # noqa: E731
        start_local = local(report["period_start"]).date()
        end_local = (local(report["period_end"]) - timedelta(microseconds=1)).date()
        pdf = self.c.get(f"/api/v1/files/{report['file_id']}/content", headers=self.owner.h)
        bad = self.c.post(
            f"{self.base}/reports",
            json={"period_start": s, "period_end": str(self.period_start + timedelta(days=2))},
            headers=self.owner.h,
        )
        self.check(
            "A report uses the requested 8–9 day range and handles missing data honestly",
            report["status"] == "ready"
            and (start_local, end_local) == (self.period_start, self.period_end)
            and pdf.content.startswith(b"%PDF-")
            and bad.status_code == 422,
            f"PDF ({len(pdf.content)} bytes) for {start_local} – {end_local}; a 3-day request is "
            "refused; missing days, the three parts (recorded / automated / caregiver-confirmed) "
            "and 'too little data' wording are checked in tests/test_reports.py",
        )

    def isolation(self) -> None:
        stranger = self.user("caregiver", "Synthetic Demo Stranger")
        probes = [
            f"{self.base}",
            f"{self.base}/analytics",
            f"{self.base}/review-items",
            f"{self.base}/sessions/{self.event_session}/events",
            f"{self.base}/memories",
        ]
        codes = [self.c.get(u, headers=stranger.h).status_code for u in probes]
        self.check(
            "Unauthorised users cannot access another patient's data",
            set(codes) == {404},
            f"another family's caregiver → {codes} (404: the patient's existence is not "
            "revealed); every patient route is swept in tests/test_authorization.py",
        )


def _tone_wav(seconds: float = 0.8, rate: int = 16000) -> bytes:
    """A synthetic 440 Hz tone (16-bit mono PCM WAV)."""
    import io
    import math
    import struct
    import wave

    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
        for i in range(int(seconds * rate))
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buffer.getvalue()


def _app(tmp: Path):
    db_url = f"sqlite:///{tmp / 'demo.db'}"
    config = alembic_config(db_url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    engine = build_engine(db_url)
    settings = Settings(
        _env_file=None,
        environment=Environment.TEST,
        database_url=db_url,
        media_root=tmp / "media",
        # Pinned so local environment variables cannot change what the demo shows.
        conversation_provider=ConversationProvider.DETERMINISTIC,
        gemini_api_key=None,
        asr_model_path=None,
        tts_model_path=None,
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_sessionmaker] = lambda: factory
    return app, engine, settings


def run(tmp: Path | None = None) -> bool:
    with tempfile.TemporaryDirectory(prefix="sneha-demo-") as scratch:
        root = tmp or Path(scratch)
        app, engine, settings = _app(root)
        try:
            with TestClient(app) as client, Session(engine, expire_on_commit=False) as db:
                return Demo(client, db, settings, app).run()
        finally:
            engine.dispose()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
