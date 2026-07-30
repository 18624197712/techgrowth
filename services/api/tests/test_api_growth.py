from techgrowth_api.domain.tasks import TaskDraft


def detailed_task() -> TaskDraft:
    return TaskDraft(
        title="验证模型接口的错误边界",
        topic="OpenAI compatible model I/O",
        expected_minutes=35,
        objective="实现可测试的模型请求与错误映射",
        curriculum_version="v1",
        track_key="ai",
        stage_key="foundation",
        node_key="ai-foundation-model-io",
        prerequisites=["能够运行 Python 测试"],
        instructions=[
            {
                "action": "为成功和鉴权失败响应创建固定测试样本",
                "minutes": 15,
                "expected_result": "两个样本都能被测试加载",
            },
            {
                "action": "实现请求并运行错误映射测试",
                "minutes": 20,
                "expected_result": "成功响应和鉴权错误均通过断言",
            },
        ],
        source_ids=["source-1"],
        submission_kinds=["commit", "report"],
        deliverables=["模型客户端实现", "测试报告"],
        acceptance_checks=[
            {
                "method": "command",
                "instruction": "pytest -q",
                "expected_result": "所有模型客户端测试通过",
            },
            {
                "method": "inspection",
                "instruction": "检查错误消息",
                "expected_result": "错误消息不包含 API Key",
            },
        ],
        rubric=[
            {
                "key": "correctness",
                "label": "实现正确性",
                "description": "请求和错误映射符合接口契约",
                "critical": True,
                "score_anchors": {
                    "0": "无法运行",
                    "1": "只能发送请求",
                    "2": "能处理成功响应",
                    "3": "能处理成功和鉴权失败",
                    "4": "额外覆盖超时且不泄露凭据",
                },
            }
        ],
        remediation_hint="修复最低分错误分支后重跑测试",
    )


def test_today_task_round_trips_curriculum_details(authenticated_client) -> None:
    client, _ = authenticated_client
    service = client.app.state.services.growth
    saved = service.save_draft(detailed_task(), "AI/LLM 工程")

    response = client.get("/api/v1/tasks/today")

    assert response.status_code == 200
    task = response.json()
    assert task["id"] == saved.id
    assert task["track_key"] == "ai"
    assert task["node_key"] == "ai-foundation-model-io"
    assert task["instructions"][0]["minutes"] == 15
    assert task["deliverables"] == ["模型客户端实现", "测试报告"]
    assert len(task["acceptance_checks"]) == 2
    assert set(task["rubric"][0]["score_anchors"]) == {"0", "1", "2", "3", "4"}


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
