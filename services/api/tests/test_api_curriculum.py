def test_curriculum_api_returns_tracks_and_progress(authenticated_client) -> None:
    client, _ = authenticated_client

    response = client.get("/api/v1/curriculum")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_track_key"] == "java"
    assert payload["algorithm_days_per_week"] == 2
    assert payload["target_stage"] == "foundation"
    assert [track["key"] for track in payload["tracks"]] == [
        "java",
        "python_ai",
        "go",
        "node_ts",
        "algorithms",
    ]
    java = payload["tracks"][0]
    assert [stage["key"] for stage in java["stages"]] == [
        "foundation", "practice", "production", "architecture"
    ]
    assert len(java["stages"][3]["nodes"]) == 3
    assert all(node["title"] for node in java["stages"][3]["nodes"])


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


def test_curriculum_api_selects_architect_difficulty_for_task(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.services.curriculum.set_algorithm_frequency(0)

    selected = client.put(
        "/api/v1/curriculum/target-stage",
        headers={"X-CSRF-Token": csrf},
        json={"stage_key": "architecture"},
    )
    generated = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "curriculum", "skill": "curriculum"},
    )

    assert selected.status_code == 200
    assert selected.json()["target_stage"] == "architecture"
    assert generated.status_code == 201
    assert generated.json()["track_key"] == "java"
    assert generated.json()["stage_key"] == "architecture"
    assert generated.json()["stage_label"] == "架构师"


def test_today_task_is_reconciled_after_switching_primary_track(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.services.curriculum.set_algorithm_frequency(0)
    first = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "curriculum", "skill": "curriculum"},
    ).json()
    assert first["track_key"] == "java"

    client.put(
        "/api/v1/curriculum/active-track",
        headers={"X-CSRF-Token": csrf},
        json={"track_key": "python_ai"},
    )
    today = client.get("/api/v1/tasks/today")

    assert today.status_code == 200
    assert today.json()["track_key"] == "python_ai"
    assert today.json()["node_key"].startswith("python_ai-")
    assert today.json()["replaces_task_id"] == first["id"]


def test_remediation_from_another_track_does_not_override_active_route(
    authenticated_client,
) -> None:
    client, csrf = authenticated_client
    client.app.state.services.curriculum.set_algorithm_frequency(0)
    client.put(
        "/api/v1/curriculum/active-track",
        headers={"X-CSRF-Token": csrf},
        json={"track_key": "python_ai"},
    )
    python_task = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "curriculum", "skill": "curriculum"},
    ).json()
    with client.app.state.database.session_factory() as db:
        from techgrowth_api.models import LearningTaskRecord

        record = db.get(LearningTaskRecord, python_task["id"])
        record.status = "remediation"
        db.commit()

    client.put(
        "/api/v1/curriculum/active-track",
        headers={"X-CSRF-Token": csrf},
        json={"track_key": "java"},
    )
    today = client.get("/api/v1/tasks/today")

    assert today.status_code == 200
    assert today.json()["track_key"] == "java"
