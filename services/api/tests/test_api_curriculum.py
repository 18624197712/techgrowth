def test_curriculum_api_returns_tracks_and_progress(authenticated_client) -> None:
    client, _ = authenticated_client

    response = client.get("/api/v1/curriculum")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_track_key"] == "java"
    assert payload["algorithm_days_per_week"] == 2
    assert [track["key"] for track in payload["tracks"]] == [
        "java",
        "python_ai",
        "go",
        "node_ts",
        "algorithms",
    ]


def test_curriculum_api_switches_primary_track(authenticated_client) -> None:
    client, csrf = authenticated_client

    response = client.put(
        "/api/v1/curriculum/active-track",
        headers={"X-CSRF-Token": csrf},
        json={"track_key": "python_ai"},
    )

    assert response.status_code == 200
    assert response.json()["active_track_key"] == "python_ai"


def test_curriculum_api_rejects_algorithm_as_primary(authenticated_client) -> None:
    client, csrf = authenticated_client

    response = client.put(
        "/api/v1/curriculum/active-track",
        headers={"X-CSRF-Token": csrf},
        json={"track_key": "algorithms"},
    )

    assert response.status_code == 422


def test_curriculum_api_updates_algorithm_frequency(authenticated_client) -> None:
    client, csrf = authenticated_client

    response = client.put(
        "/api/v1/curriculum/algorithm-frequency",
        headers={"X-CSRF-Token": csrf},
        json={"days_per_week": 3},
    )

    assert response.status_code == 200
    assert response.json()["algorithm_days_per_week"] == 3
