import pytest

from techgrowth_api.models import AppSettingRecord
from techgrowth_api.services.settings import ProviderSettings, SettingsService


def test_provider_secrets_are_encrypted_and_masked(client) -> None:
    service = SettingsService(
        client.app.state.database.session_factory,
        client.app.state.services.auth.cipher,
    )
    service.save_provider(
        ProviderSettings(
            chat={
                "base_url": "https://chat.example/v1",
                "model": "chat-model",
                "api_key": "chat-secret-key",
            },
            embedding={
                "base_url": "https://embed.example/v1",
                "model": "embed-model",
                "api_key": "embed-secret-key",
            },
        )
    )

    public = service.provider_status()
    with client.app.state.database.session_factory() as db:
        raw_database = str(db.query(AppSettingRecord).all())

    assert public == {
        "chat": {
            "base_url": "https://chat.example/v1",
            "model": "chat-model",
            "api_key_configured": True,
        },
        "embedding": {
            "base_url": "https://embed.example/v1",
            "model": "embed-model",
            "api_key_configured": True,
        },
    }
    assert "chat-secret-key" not in raw_database
    assert "embed-secret-key" not in raw_database
    assert "chat-secret-key" not in str(public)
    assert "embed-secret-key" not in str(public)


def test_empty_provider_keys_preserve_existing_encrypted_secrets(client) -> None:
    service = SettingsService(
        client.app.state.database.session_factory,
        client.app.state.services.auth.cipher,
    )
    service.save_provider(
        ProviderSettings(
            chat={
                "base_url": "https://chat.example/v1",
                "model": "chat-v1",
                "api_key": "chat-secret",
            },
            embedding={
                "base_url": "https://embed.example/v1",
                "model": "embed-v1",
                "api_key": "embed-secret",
            },
        )
    )
    before = service.provider_values()

    service.save_provider(
        ProviderSettings(
            chat={
                "base_url": "https://chat.example/v1",
                "model": "chat-v2",
                "api_key": "",
            },
            embedding={
                "base_url": "https://embed.example/v1",
                "model": "embed-v2",
                "api_key": "",
            },
        )
    )
    after = service.provider_values()

    assert after["chat.api_key"] == before["chat.api_key"] == "chat-secret"
    assert after["embedding.api_key"] == before["embedding.api_key"] == "embed-secret"
    assert after["chat.model"] == "chat-v2"
    assert after["embedding.model"] == "embed-v2"


def test_first_provider_save_requires_both_api_keys(client) -> None:
    service = SettingsService(
        client.app.state.database.session_factory,
        client.app.state.services.auth.cipher,
    )

    with pytest.raises(ValueError, match="chat API key is required"):
        service.save_provider(
            ProviderSettings(
                chat={
                    "base_url": "https://chat.example/v1",
                    "model": "chat-model",
                    "api_key": "",
                },
                embedding={
                    "base_url": "https://embed.example/v1",
                    "model": "embed-model",
                    "api_key": "embed-secret",
                },
            )
        )
