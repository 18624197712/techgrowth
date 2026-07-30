import json

from techgrowth_api.domain.curriculum import CURRICULUM
from techgrowth_api.services.chat_context import ChatContextService


def test_task_context_contains_only_whitelisted_task_fields(client) -> None:
    node = CURRICULUM.track("python_ai").nodes[0]
    draft = client.app.state.services.daily_tasks.fallback_for(node, ["source-1"])
    task = client.app.state.services.growth.save_draft(draft, node.title)
    service = ChatContextService(client.app.state.database.session_factory)

    context = service.build(
        "task_coaching",
        {
            "task_id": task.id,
            "api_key": "secret-value",
            "session_token": "session-secret",
            "private_key": "private-secret",
        },
    )

    rendered = json.dumps(context, ensure_ascii=False)
    assert context["task"]["id"] == task.id
    assert context["task"]["rubric"]
    assert "secret-value" not in rendered
    assert "session-secret" not in rendered
    assert "private-secret" not in rendered


def test_growth_context_is_bounded(client) -> None:
    service = ChatContextService(client.app.state.database.session_factory)

    context = service.build("growth_planning", {"view": "profile"})

    assert set(context) == {"page", "skills", "curriculum_progress"}
    assert len(json.dumps(context, ensure_ascii=False)) <= 12_000
