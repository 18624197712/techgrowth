import asyncio
import json
from email.message import EmailMessage

import aiosmtplib
from pywebpush import webpush
from sqlalchemy import select

from ..config import Settings
from ..crypto import SecretCipher
from ..models import (
    NotificationDeliveryRecord,
    NotificationPreferenceRecord,
    PushSubscriptionRecord,
    User,
)

EVENT_BODIES = {
    "daily_task": "今日成长任务已准备好。",
    "review_complete": "审阅已完成，登录 TechGrowth 查看结果。",
    "weekly_review": "本周成长复盘已生成。",
}


def safe_notification(
    event: str, title: str, app_url: str, sensitive_body: str = ""
) -> dict[str, str]:
    del sensitive_body
    return {
        "title": title[:120],
        "body": EVENT_BODIES.get(event, "TechGrowth 有一条新进展。"),
        "url": app_url,
    }


class NotificationService:
    def __init__(self, settings: Settings, session_factory, cipher: SecretCipher) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.cipher = cipher

    async def dispatch(
        self,
        event: str,
        title: str,
        app_url: str,
        sensitive_body: str = "",
    ) -> None:
        payload = safe_notification(event, title, app_url, sensitive_body)
        with self.session_factory() as db:
            preferences = db.scalars(
                select(NotificationPreferenceRecord).where(
                    NotificationPreferenceRecord.event == event,
                    NotificationPreferenceRecord.enabled.is_(True),
                )
            ).all()
            user = db.scalar(select(User))
            encrypted_subscriptions = [
                item.subscription_enc for item in db.scalars(select(PushSubscriptionRecord)).all()
            ]

        for preference in preferences:
            if preference.channel == "email":
                if not self.settings.smtp_host or not user:
                    self._record(event, "email", "skipped")
                    continue
                try:
                    await self.send_email(user.email, payload)
                except Exception as exc:
                    self._record(event, "email", "failed", str(exc))
                else:
                    self._record(event, "email", "sent")
            elif preference.channel == "web_push":
                if not self.settings.vapid_private_key or not encrypted_subscriptions:
                    self._record(event, "web_push", "skipped")
                    continue
                for encrypted in encrypted_subscriptions:
                    try:
                        subscription = json.loads(self.cipher.decrypt(encrypted))
                        await self.send_web_push(subscription, payload)
                    except Exception as exc:
                        self._record(event, "web_push", "failed", str(exc))
                    else:
                        self._record(event, "web_push", "sent")

    def _record(self, event: str, channel: str, status: str, error: str = "") -> None:
        with self.session_factory() as db:
            db.add(
                NotificationDeliveryRecord(
                    event=event, channel=channel, status=status, error=error[:500]
                )
            )
            db.commit()

    async def send_email(self, destination: str, payload: dict[str, str]) -> None:
        if not self.settings.smtp_host:
            return
        message = EmailMessage()
        message["From"] = self.settings.smtp_sender
        message["To"] = destination
        message["Subject"] = payload["title"]
        message.set_content(f"{payload['body']}\n\n{payload['url']}")
        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username or None,
            password=self.settings.smtp_password or None,
            start_tls=self.settings.smtp_port != 465,
            use_tls=self.settings.smtp_port == 465,
        )

    async def send_web_push(self, subscription: dict, payload: dict[str, str]) -> None:
        if not self.settings.vapid_private_key:
            return
        await asyncio.to_thread(
            webpush,
            subscription_info=subscription,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=self.settings.vapid_private_key,
            vapid_claims={"sub": self.settings.vapid_subject},
        )
