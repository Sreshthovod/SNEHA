from tests.helpers import Api, iso, now


def test_observations_crud_and_author_rules(api: Api) -> None:
    owner, helper = api.user(), api.user()
    pid = api.patient(owner)
    api.add_caregiver(owner, pid, helper)
    url = f"/api/v1/patients/{pid}/observations"

    mine = api.client.post(
        url,
        json={"observed_at": iso(now()), "category": "sleep", "note": "Slept well"},
        headers=helper.headers,
    )
    assert mine.status_code == 201
    owners = api.client.post(
        url,
        json={"observed_at": iso(now()), "category": "mood", "note": "Cheerful"},
        headers=owner.headers,
    ).json()

    assert len(api.client.get(url, headers=owner.headers).json()) == 2
    # Non-managing helper cannot delete someone else's note; can delete own.
    assert api.client.delete(f"{url}/{owners['id']}", headers=helper.headers).status_code == 403
    assert (
        api.client.delete(f"{url}/{mine.json()['id']}", headers=helper.headers).status_code == 204
    )


def test_observation_validation(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    url = f"/api/v1/patients/{pid}/observations"
    for body in [
        {"observed_at": iso(now()), "category": "diagnosis", "note": "x"},
        {"observed_at": iso(now()), "category": "mood", "note": ""},
        {"observed_at": iso(now()), "category": "mood", "note": "x" * 2001},
        {"observed_at": "yesterday", "category": "mood", "note": "x"},
    ]:
        assert api.client.post(url, json=body, headers=owner.headers).status_code == 422


def test_routines(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner)
    device = api.pair_device(owner, pid)
    url = f"/api/v1/patients/{pid}/routines"
    created = api.client.post(
        url,
        json={"title": "Morning tea", "local_time": "07:30", "days_of_week": 127},
        headers=owner.headers,
    )
    assert created.status_code == 201
    assert [r["title"] for r in api.client.get(url, headers=device.headers).json()] == [
        "Morning tea"
    ]
    for bad in [
        {"local_time": "25:00"},
        {"local_time": "7:30"},
        {"days_of_week": 0},
        {"days_of_week": 128},
    ]:
        body = {"title": "X", "local_time": "08:00", "days_of_week": 1, **bad}
        assert api.client.post(url, json=body, headers=owner.headers).status_code == 422
    assert (
        api.client.delete(f"{url}/{created.json()['id']}", headers=owner.headers).status_code == 204
    )


def test_report_requests_must_cover_8_or_9_days(api: Api) -> None:
    owner = api.user()
    pid = api.patient(owner, timezone="Asia/Kolkata")
    url = f"/api/v1/patients/{pid}/reports"
    ok8 = api.client.post(
        url, json={"period_start": "2026-10-01", "period_end": "2026-10-08"}, headers=owner.headers
    )
    ok9 = api.client.post(
        url, json={"period_start": "2026-10-01", "period_end": "2026-10-09"}, headers=owner.headers
    )
    assert (ok8.status_code, ok9.status_code) == (201, 201)
    assert ok8.json()["status"] == "ready"
    assert ok8.json()["file_id"] is not None
    # Period boundaries are local midnight in the patient's timezone.
    assert ok8.json()["period_start"].startswith("2026-09-30T18:30:00")

    for start, end in [
        ("2026-10-01", "2026-10-07"),
        ("2026-10-01", "2026-10-10"),
        ("2026-10-08", "2026-10-01"),
    ]:
        bad = api.client.post(
            url, json={"period_start": start, "period_end": end}, headers=owner.headers
        )
        assert bad.status_code == 422

    listed = api.client.get(url, headers=owner.headers).json()
    assert len(listed) == 2
    one = api.client.get(f"{url}/{ok8.json()['id']}", headers=owner.headers)
    assert one.status_code == 200


def test_config_status_is_honest_about_unimplemented_features(api: Api) -> None:
    caregiver = api.user()
    assert api.client.get("/api/v1/config/status").status_code == 401
    status = api.client.get("/api/v1/config/status", headers=caregiver.headers).json()
    features = {f["name"]: f for f in status["features"]}
    assert features["conversation_understanding"]["available"] is True
    assert features["conversation_understanding"]["mode"] == "deterministic"
    assert features["report_generation"]["available"] is True
    assert features["sync"]["available"] is True
    assert "as" in status["supported_languages"]
    assert status["report_period_days"] == [8, 9]
