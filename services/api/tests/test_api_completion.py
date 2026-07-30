import json

from techgrowth_api.chat_workflow import ChatIntentDecision
from techgrowth_api.integrations.model_client import ModelClientError


class StaticChatModel:
    async def structured(self, system_prompt, user_prompt, output_model):
        return ChatIntentDecision(intent="task_coaching", confidence=0.91)

    async def complete(self, system_prompt, user_prompt):
        return "先运行验收命令，再根据最低分 Rubric 补充证据。"


class FailingChatModel(StaticChatModel):
    async def complete(self, system_prompt, user_prompt):
        raise ModelClientError("模型服务鉴权失败", "provider_auth")


def event_names(body: str) -> list[str]:
    return [
        line.removeprefix("event: ") for line in body.splitlines() if line.startswith("event: ")
    ]


def test_chat_stream_emits_real_model_answer_and_typed_events(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.model_client_factory = lambda settings: StaticChatModel()
    task = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "ignored", "skill": "ignored"},
    ).json()

    chat = client.post(
        "/api/v1/chat/stream",
        headers={"X-CSRF-Token": csrf},
        json={"message": "我该怎么改进？", "page_context": {"task_id": task["id"]}},
    )

    assert chat.headers["content-type"].startswith("text/event-stream")
    assert event_names(chat.text)[0] == "intent"
    assert "先运行验收命令" in chat.text
    assert event_names(chat.text)[-1] == "done"
    assert "我已收到问题" not in chat.text


def test_chat_stream_emits_safe_provider_error(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.model_client_factory = lambda settings: FailingChatModel()

    chat = client.post(
        "/api/v1/chat/stream",
        headers={"X-CSRF-Token": csrf},
        json={"message": "解释事务隔离", "page_context": {}},
    )

    assert event_names(chat.text) == ["error", "done"]
    error_event = next(block for block in chat.text.split("\n\n") if "event: error" in block)
    payload = json.loads(
        next(line[6:] for line in error_event.splitlines() if line.startswith("data: "))
    )
    assert payload == {"code": "provider_auth", "message": "模型服务鉴权失败"}


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
