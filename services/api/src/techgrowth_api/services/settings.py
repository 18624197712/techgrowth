from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select

from ..crypto import SecretCipher
from ..models import AppSettingRecord


class ProviderEndpointSettings(BaseModel):
    base_url: HttpUrl
    model: str = Field(min_length=1)
    api_key: str = ""


class ProviderSettings(BaseModel):
    chat: ProviderEndpointSettings
    embedding: ProviderEndpointSettings


class ProviderSettingsValidationError(ValueError):
    pass


class SettingsService:
    CAPABILITIES = ("chat", "embedding")
    ENDPOINT_KEYS = ("base_url", "model", "api_key")
    LEGACY_KEYS = ("base_url", "chat_model", "embedding_model", "api_key")
    KEYS = (
        "chat.base_url",
        "chat.model",
        "chat.api_key",
        "embedding.base_url",
        "embedding.model",
        "embedding.api_key",
    ) + LEGACY_KEYS

    def __init__(self, session_factory, cipher: SecretCipher) -> None:
        self.session_factory = session_factory
        self.cipher = cipher

    def save_provider(self, settings: ProviderSettings) -> None:
        values = settings.model_dump(mode="json")
        with self.session_factory() as db:
            for capability in self.CAPABILITIES:
                incoming_key = values[capability]["api_key"]
                stored_key = db.get(AppSettingRecord, f"provider.{capability}.api_key")
                legacy_key = db.get(AppSettingRecord, "provider.api_key")
                if not incoming_key and not stored_key and not legacy_key:
                    raise ProviderSettingsValidationError(
                        f"{capability} API key is required"
                    )

            for capability in self.CAPABILITIES:
                for key in self.ENDPOINT_KEYS:
                    value = values[capability][key]
                    record_key = f"provider.{capability}.{key}"
                    record = db.get(AppSettingRecord, record_key)
                    if key == "api_key" and not value:
                        continue
                    encrypted = self.cipher.encrypt(str(value))
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

    def provider_status(self) -> dict[str, dict[str, str | bool]]:
        values = self.provider_values()
        return {
            capability: {
                "base_url": values.get(
                    f"{capability}.base_url", values.get("base_url", "")
                ),
                "model": values.get(
                    f"{capability}.model",
                    values.get(f"{capability}_model", ""),
                ),
                "api_key_configured": bool(
                    values.get(f"{capability}.api_key", values.get("api_key", ""))
                ),
            }
            for capability in self.CAPABILITIES
        }
