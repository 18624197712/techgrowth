from sqlalchemy import select

from techgrowth_api.models import LearningTaskRecord


def _generate(client, csrf):
    response = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "ignored", "skill": "ignored"},
    )
    assert response.status_code == 201
    return response.json()


def test_task_hints_and_solution_are_hidden_until_revealed(authenticated_client) -> None:
    client, csrf = authenticated_client
    task = _generate(client, csrf)

    assert task["revealed_hints"] == []
    assert task["solution_outline"] is None

    hint = client.post(
        f"/api/v1/tasks/{task['id']}/hints/1/reveal",
        headers={"X-CSRF-Token": csrf},
    )
    assert hint.status_code == 200
    assert len(hint.json()["revealed_hints"]) == 1

    solution = client.post(
        f"/api/v1/tasks/{task['id']}/solution/reveal",
        headers={"X-CSRF-Token": csrf},
    )
    assert solution.status_code == 200
    assert len(solution.json()["solution_outline"]) >= 20


def test_missing_guidance_is_repaired_from_the_curriculum_template(
    authenticated_client,
) -> None:
    client, csrf = authenticated_client
    task = _generate(client, csrf)
    with client.app.state.database.session_factory() as db:
        record = db.get(LearningTaskRecord, task["id"])
        record.hints = []
        record.solution_outline = ""
        db.commit()

    hint = client.post(
        f"/api/v1/tasks/{task['id']}/hints/1/reveal",
        headers={"X-CSRF-Token": csrf},
    )
    solution = client.post(
        f"/api/v1/tasks/{task['id']}/solution/reveal",
        headers={"X-CSRF-Token": csrf},
    )

    assert hint.status_code == 200
    assert hint.json()["guidance_source"] == "curriculum_template"
    assert len(hint.json()["revealed_hints"]) == 1
    assert solution.status_code == 200
    assert len(solution.json()["solution_outline"]) >= 20


def test_regeneration_replaces_open_task_and_is_idempotent(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.services.curriculum.set_algorithm_frequency(0)
    original = _generate(client, csrf)
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "regen-clearer-task"}

    first = client.post(
        f"/api/v1/tasks/{original['id']}/regenerate",
        headers=headers,
        json={"reason": "题目不够明确"},
    )
    second = client.post(
        f"/api/v1/tasks/{original['id']}/regenerate",
        headers=headers,
        json={"reason": "题目不够明确"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["replaces_task_id"] == original["id"]
    assert first.json()["node_key"] == original["node_key"]
    assert first.json()["track_key"] == "java"
    assert first.json()["stage_key"] == "foundation"
    assert first.json()["title"] != original["title"]
    assert first.json()["generation_source"] in {"ai", "rules"}
    with client.app.state.database.session_factory() as db:
        old = db.scalar(select(LearningTaskRecord).where(LearningTaskRecord.id == original["id"]))
        assert old.status == "replaced"


def test_regeneration_uses_current_track_instead_of_stale_task_track(
    authenticated_client,
) -> None:
    client, csrf = authenticated_client
    client.app.state.services.curriculum.set_algorithm_frequency(0)
    original = _generate(client, csrf)
    assert original["track_key"] == "java"

    switched = client.put(
        "/api/v1/curriculum/active-track",
        headers={"X-CSRF-Token": csrf},
        json={"track_key": "go"},
    )
    assert switched.status_code == 200

    regenerated = client.post(
        f"/api/v1/tasks/{original['id']}/regenerate",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "regen-current-go"},
        json={"reason": "按当前课程重新出题"},
    )

    assert regenerated.status_code == 201
    payload = regenerated.json()
    assert payload["track_key"] == "go"
    assert payload["node_key"].startswith("go-")
    assert payload["stage_key"] == "foundation"
    assert payload["node_order"] == 1
    assert payload["node_total"] == 12
    assert payload["track_label"] == "Go"


def test_regeneration_rejects_submitted_task(authenticated_client) -> None:
    client, csrf = authenticated_client
    task = _generate(client, csrf)
    scores = {criterion["key"]: 4 for criterion in task["rubric"]}
    submitted = client.post(
        f"/api/v1/tasks/{task['id']}/submissions",
        headers={"X-CSRF-Token": csrf},
        json={
            "summary": "完成实现并运行全部验收测试",
            "artifact_kind": "answer",
            "artifact_reference": "report.md",
            "self_scores": scores,
        },
    )
    assert submitted.status_code == 201

    response = client.post(
        f"/api/v1/tasks/{task['id']}/regenerate",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "regen-submitted"},
        json={"reason": "换一道题"},
    )

    assert response.status_code == 409
