"""Seed a running dev API with one SYNTHETIC family for UI screenshots.

Uses only the public HTTP API (no database access). Every name says "Synthetic".
Prints the caregiver/clinician logins and patient ID as JSON on the last line.

    python3 -I tools/ui-qa/seed_synthetic.py http://127.0.0.1:8000
"""

import json
import pathlib
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import zlib
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000") + "/api/v1"
TZ = ZoneInfo("Asia/Kolkata")
PAIRS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0001"
OBJECTS = "4b0c2d0e-5f0e-4c39-9d43-1a6f3f0a0009"
PASSWORD = "synthetic-ui-qa-password"  # noqa: S105 - local synthetic account


def call(method, path, body=None, token=None, raw=None, ctype="application/json"):
    headers = {}
    data = None
    if raw is not None:
        data, headers["Content-Type"] = raw, ctype
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            text = r.read()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} -> {e.code}: {e.read()[:300]!r}") from e


def png(w, h, top, bottom):
    """A soft vertical gradient: a stand-in photo (no real person)."""
    rows = []
    for y in range(h):
        t = y / max(h - 1, 1)
        px = bytes(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
        rows.append(b"\x00" + px * w)
    def chunk(kind, payload):
        c = struct.pack(">I", len(payload)) + kind + payload
        return c + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")


def multipart(name, filename, content, ctype):
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def iso(d):
    return d.astimezone(UTC).isoformat().replace("+00:00", "Z")


def account(role, name):
    email = f"synthetic.uiqa.{role}.{uuid.uuid4().hex[:6]}@example.org"
    call("POST", "/auth/register", {"email": email, "password": PASSWORD, "full_name": name, "role": role})
    token = call("POST", "/auth/login", {"email": email, "password": PASSWORD})["access_token"]
    return email, token


owner_email, owner = account("caregiver", "Synthetic Anjali Bora")
pid = call("POST", "/patients", {"display_name": "Synthetic Grandmother Bora", "preferred_name": "Aita",
                                  "preferred_language": "as", "relationship_label": "daughter",
                                  "timezone": "Asia/Kolkata", "region": "Assam", "birth_year": 1948}, owner)["id"]
P = f"/patients/{pid}"
for consent in ("data_processing", "clinician_sharing"):
    call("POST", f"{P}/consents", {"consent_type": consent, "status": "granted", "given_by": "legal_representative"}, owner)
call("PUT", f"{P}/preferences", {"interests": ["tea", "family", "festivals"], "disliked_activity_slugs": [], "session_minutes": 15}, owner)

colors = [((216, 196, 160), (120, 140, 110)), ((180, 205, 190), (70, 110, 90)),
          ((240, 210, 180), (200, 120, 90)), ((200, 210, 225), (110, 120, 150))]
memories = [
    ("person", "Synthetic Mina, granddaughter", "Visits on Sundays and brings sweets.", ["family", "mina"], 2015),
    ("place", "Synthetic tea garden at Jorhat", "Where the family picked tea every spring.", ["tea", "garden"], 1972),
    ("event", "Synthetic Bihu festival", "Dancing in the courtyard with neighbours.", ["festivals", "bihu"], 1985),
    ("place", "Synthetic old village house", "The house with the bamboo gate.", ["home"], 1960),
]
for i, (kind, title, desc, tags, year) in enumerate(memories):
    body, ctype = multipart("file", "synthetic.png", png(64, 48, *colors[i]), "image/png")
    photo = call("POST", f"{P}/media", raw=body, ctype=ctype, token=owner)
    call("POST", f"{P}/memories", {"kind": kind, "title": title, "description": desc, "tags": tags,
                                   "approx_year": year, "media_file_id": photo["id"]}, owner)

helper_email, helper = account("caregiver", "Synthetic Neighbour Das")
call("POST", f"{P}/caregivers", {"email": helper_email, "relationship_label": "neighbour", "can_manage": False}, owner)
call("POST", f"{P}/memories", {"kind": "person", "title": "Synthetic cousin from Tezpur", "tags": ["family"]}, helper)

code = call("POST", f"{P}/pairing-codes", token=owner)["code"]
device = call("POST", "/auth/device/pair", {"code": code, "device_name": "Synthetic phone"})["access_token"]

today = datetime.now(TZ).date()
mut = []
def session(day, hour, score, rt, hints, activity=PAIRS, end="completed", tired=False):
    sid = str(uuid.uuid4())
    start = datetime.combine(day, datetime.min.time(), TZ) + timedelta(hours=hour)
    mut.append({"mutation_id": str(uuid.uuid4()), "entity_type": "activity_session",
                "data": {"id": sid, "started_at": iso(start), "ended_at": iso(start + timedelta(minutes=7)),
                         "status": "completed" if end == "completed" else "abandoned", "end_reason": end}})
    mut.append({"mutation_id": str(uuid.uuid4()), "entity_type": "activity_result",
                "data": {"id": str(uuid.uuid4()), "session_id": sid, "activity_id": activity, "difficulty_level": 2,
                         "started_at": iso(start + timedelta(minutes=1)), "completed_at": iso(start + timedelta(minutes=6)),
                         "score": None if tired else score, "correct_count": 4, "attempt_count": 6, "hint_count": hints,
                         "duration_ms": 300000, "abandoned": tired, "fatigue_reported": tired,
                         "engagement": "enjoyed" if score > 0.7 else "neutral",
                         "metrics": {"mean_response_ms": rt}}})
    return sid, start

for d in range(30, 9, -1):
    if d % 3:
        session(today - timedelta(days=d), 10, 0.9, 2100, 0)
last = None
for d in range(8, -1, -1):
    if d in (5, 2):
        continue
    day = today - timedelta(days=d)
    last = session(day, 10, 0.6 if d < 7 else 0.85, 3200, 1, activity=OBJECTS if d % 2 else PAIRS)
    if d == 3:
        session(day, 16, 0.5, 3000, 2, end="fatigue_detected", tired=True)
sid, start = last
steps = [("activity_started", None, {"rounds_planned": 4, "difficulty": 2}),
         ("attempt", 0, {"correct": False, "latency_ms": 4200}), ("attempt", 0, {"correct": False, "latency_ms": 5100}),
         ("adaptation", 0, {"action": "show_hint", "reason_codes": ["REPEATED_ERRORS_IN_ROUND"]}),
         ("hint_auto", 0, {"hint_number": 1, "source": "system"}), ("attempt", 0, {"correct": True, "latency_ms": 2600}),
         ("round_solved", 0, {}), ("activity_ended", None, {"outcome": "completed"})]
for i, (kind, rnd, data) in enumerate(steps):
    mut.append({"mutation_id": str(uuid.uuid4()), "entity_type": "activity_event",
                "data": {"id": str(uuid.uuid4()), "session_id": sid, "activity_id": OBJECTS if (today - start.date()).days % 2 else PAIRS,
                         "seq": i, "event_type": kind, "occurred_at": iso(start + timedelta(minutes=1, seconds=15 * i)),
                         "round_index": rnd, "data": data}})
for i in range(0, len(mut), 200):
    call("POST", "/sync/push", {"device_install_id": str(uuid.uuid4()), "mutations": mut[i:i + 200]}, device)

call("POST", f"{P}/observations", {"observed_at": iso(datetime.now(UTC) - timedelta(days=3, hours=2)), "category": "fatigue",
                                    "fatigue_level": "mild", "note": "Synthetic: sleepy after lunch, rested for an hour."}, owner)
call("POST", f"{P}/observations", {"observed_at": iso(datetime.now(UTC) - timedelta(days=1)), "category": "mood",
                                    "note": "Synthetic: cheerful after Mina's visit."}, owner)
start_d, end_d = today - timedelta(days=8), today
call("POST", f"{P}/review-items/scan", {"period_start": str(start_d), "period_end": str(end_d)}, owner)
call("POST", f"{P}/reports", {"period_start": str(start_d - timedelta(days=1)), "period_end": str(end_d - timedelta(days=1))}, owner)

clin_email, clin = account("clinician", "Synthetic Dr. Baruah")
# The documented admin path (an administrator verifies clinicians).
api_dir = pathlib.Path(__file__).resolve().parents[2] / "services" / "api"
subprocess.run(["uv", "run", "python", "scripts/manage.py", "verify-clinician", clin_email],
               cwd=api_dir, check=True, capture_output=True)
call("POST", f"{P}/clinician-grants", {"clinician_email": clin_email, "expires_at": iso(datetime.now(UTC) + timedelta(days=30)),
                                       "purpose": "Synthetic memory clinic follow-up"}, owner)
print(json.dumps({"patient_id": pid, "caregiver": owner_email, "helper": helper_email,
                  "clinician": clin_email, "password": PASSWORD}))
