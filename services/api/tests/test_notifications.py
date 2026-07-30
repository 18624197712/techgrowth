import pytest
from sqlalchemy import select

from techgrowth_api.models import NotificationDeliveryRecord
from techgrowth_api.services.notifications import NotificationService, safe_notification


def test_notification_never_contains_code_or_review_body() -> None:
    payload = safe_notification(
        event="review_complete",
        title="RAG evaluator review",
        app_url="https://coach.example.com/tasks/1",
        sensitive_body="API_KEY=secret\nfull review text",
    )

    assert payload["body"] == "审阅已完成，登录 TechGrowth 查看结果。"
    assert "secret" not in str(payload)
    assert payload["url"].startswith("https://")


@pytest.mark.asyncio
async def test_enabled_email_notification_is_delivered_and_audited(
    authenticated_client, settings
) -> None:
    client, csrf = authenticated_client
    client.put(
        "/api/v1/notifications/preferences",
        headers={"X-CSRF-Token": csrf},
        json={"preferences": [{"channel": "email", "event": "daily_task", "enabled": True}]},
    )
    delivered: list[tuple[str, dict]] = []
    configured = settings.model_copy(
        update={"smtp_host": "smtp.example.com", "smtp_sender": "growth@example.com"}
    )
    service = NotificationService(
        configured,
        client.app.state.database.session_factory,
        client.app.state.services.auth.cipher,
    )

    async def capture(destination: str, payload: dict[str, str]) -> None:
        delivered.append((destination, payload))

    service.send_email = capture
    await service.dispatch(
        "daily_task", "今日任务", "https://growth.example.com", sensitive_body="secret"
    )

    assert delivered[0][0] == "developer@example.com"
    assert "secret" not in str(delivered)
    with client.app.state.database.session_factory() as db:
        audit = db.scalar(select(NotificationDeliveryRecord))
        assert audit.event == "daily_task"
        assert audit.channel == "email"
        assert audit.status == "sent"
