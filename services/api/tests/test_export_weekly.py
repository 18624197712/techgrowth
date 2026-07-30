def test_export_and_weekly_review_are_authenticated(authenticated_client) -> None:
    client, csrf = authenticated_client
    task = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "Agent 评测", "skill": "Agent evaluation"},
    ).json()
    client.post(
        f"/api/v1/tasks/{task['id']}/submissions",
        headers={"X-CSRF-Token": csrf},
        json={
            "summary": "完成固定样例评测",
            "artifact_kind": "commit",
            "artifact_reference": "def456",
            "self_scores": {"correctness": 3, "testing": 4},
        },
    )

    weekly = client.post("/api/v1/weekly-reviews/generate", headers={"X-CSRF-Token": csrf})
    exported = client.get("/api/v1/export")

    assert weekly.status_code == 201
    assert weekly.json()["evidence_ids"]
    assert exported.status_code == 200
    assert exported.json()["skills"][0]["name"] == task["skill_name"]
