import json
from datetime import UTC, datetime, timedelta

from techgrowth_api.chat_workflow import ChatIntentDecision
from techgrowth_api.models import AgentActionRecord


class RadarActionModel:
    async def structured(self, system_prompt, user_prompt, output_model):
        return ChatIntentDecision(intent="radar_to_task", confidence=0.96, needs_action=True)

    async def complete(self, system_prompt, user_prompt):
        return "我可以把这个信号转成课程兼容任务，确认后才会创建。"


def action_payload(body: str) -> dict:
    block = next(item for item in body.split("\n\n") if "event: action_proposal" in item)
    return json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: ")))


def test_radar_action_requires_confirmation_and_is_idempotent(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.model_client_factory = lambda settings: RadarActionModel()
    radar = client.get("/api/v1/radar").json()[0]

    chat = client.post(
        "/api/v1/chat/stream",
        headers={"X-CSRF-Token": csrf},
        json={
            "message": "把这个雷达条目转成任务",
            "page_context": {"radar_item_id": radar["id"]},
        },
    )
    proposal = action_payload(chat.text)
    assert client.get("/api/v1/tasks/today").status_code == 404

    first = client.post(
        f"/api/v1/chat/actions/{proposal['id']}/confirm",
        headers={"X-CSRF-Token": csrf},
    )
    second = client.post(
        f"/api/v1/chat/actions/{proposal['id']}/confirm",
        headers={"X-CSRF-Token": csrf},
    )

    assert first.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["curriculum_version"] == "v1"


def test_expired_chat_action_is_rejected(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.model_client_factory = lambda settings: RadarActionModel()
    radar = client.get("/api/v1/radar").json()[0]
    chat = client.post(
        "/api/v1/chat/stream",
        headers={"X-CSRF-Token": csrf},
        json={
            "message": "转成任务",
            "page_context": {"radar_item_id": radar["id"]},
        },
    )
    proposal = action_payload(chat.text)
    with client.app.state.database.session_factory() as db:
        action = db.get(AgentActionRecord, proposal["id"])
        action.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    response = client.post(
        f"/api/v1/chat/actions/{proposal['id']}/confirm",
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 410
