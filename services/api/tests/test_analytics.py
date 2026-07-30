import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/overview?range=30d",
        "/api/v1/analytics/learning?range=30d",
        "/api/v1/analytics/radar?range=30d",
        "/api/v1/analytics/repositories?range=30d",
        "/api/v1/analytics/ai-runs?range=30d",
    ],
)
def test_analytics_views_return_explainable_metrics(authenticated_client, path) -> None:
    client, _ = authenticated_client

    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["range"] == "30d"
    assert isinstance(payload["metrics"], list)
    assert all(
        {"key", "label", "value", "unit", "definition", "components"} <= set(metric)
        for metric in payload["metrics"]
    )


def test_overview_reflects_generated_and_reviewed_task(authenticated_client) -> None:
    client, csrf = authenticated_client
    task = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "ignored", "skill": "ignored"},
    ).json()
    client.post(
        f"/api/v1/tasks/{task['id']}/submissions",
        headers={"X-CSRF-Token": csrf},
        json={
            "summary": "完成任务并记录测试结果",
            "artifact_kind": "answer",
            "artifact_reference": "report.md",
            "self_scores": {item["key"]: 4 for item in task["rubric"]},
        },
    )

    payload = client.get("/api/v1/analytics/overview?range=7d").json()
    metrics = {item["key"]: item for item in payload["metrics"]}

    assert metrics["learning_minutes"]["value"] == task["expected_minutes"]
    assert metrics["task_pass_rate"]["value"] == 100
    assert metrics["task_pass_rate"]["components"]["reviewed"] == 1


def test_analytics_rejects_unknown_range(authenticated_client) -> None:
    client, _ = authenticated_client

    response = client.get("/api/v1/analytics/overview?range=13d")

    assert response.status_code == 422
