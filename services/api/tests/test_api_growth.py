def test_daily_task_submission_creates_review_and_evidence(authenticated_client) -> None:
    client, csrf = authenticated_client
    task_response = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "RAG 评测", "skill": "RAG evaluation"},
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert 30 <= task["expected_minutes"] <= 45
    assert task["rubric"]

    submitted = client.post(
        f"/api/v1/tasks/{task['id']}/submissions",
        headers={"X-CSRF-Token": csrf},
        json={
            "summary": "实现了带固定样例的检索评测器",
            "artifact_kind": "commit",
            "artifact_reference": "abc123",
            "self_scores": {"correctness": 3, "testing": 3},
        },
    )
    assert submitted.status_code == 201
    review = submitted.json()["review"]
    assert review["passed"] is True

    profile = client.get("/api/v1/profile").json()
    skill = next(item for item in profile if item["name"] == "RAG evaluation")
    assert skill["level"] == "practicing"
    assert skill["evidence_count"] == 1


def test_radar_endpoint_returns_seeded_sources_with_relevance(authenticated_client) -> None:
    client, _ = authenticated_client
    response = client.get("/api/v1/radar")
    assert response.status_code == 200
    assert response.json()[0]["source_url"].startswith("https://")
    assert response.json()[0]["relevance_reason"]
