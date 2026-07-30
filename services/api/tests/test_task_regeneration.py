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


def test_regeneration_replaces_open_task_and_is_idempotent(authenticated_client) -> None:
    client, csrf = authenticated_client
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
    with client.app.state.database.session_factory() as db:
        old = db.scalar(select(LearningTaskRecord).where(LearningTaskRecord.id == original["id"]))
        assert old.status == "replaced"


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
