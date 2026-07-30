from datetime import UTC, datetime

from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

from ..crypto import SecretCipher
from ..models import AppSettingRecord


class ProviderSettings(BaseModel):
    base_url: HttpUrl
    chat_model: str
    embedding_model: str
    api_key: str


class SettingsService:
    KEYS = ("base_url", "chat_model", "embedding_model", "api_key")

    def __init__(self, session_factory, cipher: SecretCipher) -> None:
        self.session_factory = session_factory
        self.cipher = cipher

    def save_provider(self, settings: ProviderSettings) -> None:
        values = settings.model_dump(mode="json")
        with self.session_factory() as db:
            for key in self.KEYS:
                record_key = f"provider.{key}"
                record = db.get(AppSettingRecord, record_key)
                encrypted = self.cipher.encrypt(str(values[key]))
                if record:
                    record.value_enc = encrypted
                    record.updated_at = datetime.now(UTC)
                else:
                    db.add(AppSettingRecord(key=record_key, value_enc=encrypted))
            db.commit()

    def provider_values(self) -> dict[str, str]:
        with self.session_factory() as db:
            records = db.scalars(
                select(AppSettingRecord).where(
                    AppSettingRecord.key.in_([f"provider.{key}" for key in self.KEYS])
                )
            ).all()
            return {
                item.key.removeprefix("provider."): self.cipher.decrypt(item.value_enc)
                for item in records
            }

    def provider_status(self) -> dict[str, str | bool]:
        values = self.provider_values()
        return {
            "base_url": values.get("base_url", ""),
            "chat_model": values.get("chat_model", ""),
            "embedding_model": values.get("embedding_model", ""),
            "api_key_configured": bool(values.get("api_key")),
        }
