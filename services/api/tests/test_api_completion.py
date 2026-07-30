def test_today_review_weekly_and_chat_endpoints(authenticated_client) -> None:
    client, csrf = authenticated_client
    assert client.get("/api/v1/tasks/today").status_code == 404
    task = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "RAG 可靠性", "skill": "RAG engineering"},
    ).json()
    submission = client.post(
        f"/api/v1/tasks/{task['id']}/submissions",
        headers={"X-CSRF-Token": csrf},
        json={
            "summary": "实现并验证了检索失败样例",
            "artifact_kind": "commit",
            "artifact_reference": "abc999",
            "self_scores": {"correctness": 3, "testing": 4},
        },
    ).json()
    client.post("/api/v1/weekly-reviews/generate", headers={"X-CSRF-Token": csrf})

    assert client.get("/api/v1/tasks/today").json()["id"] == task["id"]
    assert client.get(f"/api/v1/reviews/{submission['id']}").json()["passed"] is True
    assert client.get("/api/v1/weekly-reviews").json()[0]["evidence_ids"]
    chat = client.post(
        "/api/v1/chat/stream",
        headers={"X-CSRF-Token": csrf},
        json={"message": "我该怎么改进？", "page_context": {"task_id": task["id"]}},
    )
    assert chat.headers["content-type"].startswith("text/event-stream")
    assert "data:" in chat.text


def test_push_subscription_and_growth_data_deletion(authenticated_client) -> None:
    client, csrf = authenticated_client
    subscribed = client.post(
        "/api/v1/notifications/push-subscriptions",
        headers={"X-CSRF-Token": csrf},
        json={
            "endpoint": "https://push.example/subscription/1",
            "keys": {"p256dh": "public-key", "auth": "auth-key"},
        },
    )
    deleted = client.request(
        "DELETE",
        "/api/v1/data",
        headers={"X-CSRF-Token": csrf},
        json={"confirmation": "DELETE MY GROWTH DATA"},
    )

    assert subscribed.status_code == 201
    assert deleted.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200
