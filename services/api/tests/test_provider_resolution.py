from techgrowth_api.config import Settings
from techgrowth_api.worker import resolve_provider_settings


def test_provider_specific_stored_values_have_highest_precedence() -> None:
    settings = Settings(
        chat_base_url="https://chat-env.example/v1",
        chat_api_key="chat-env-key",
        embedding_base_url="https://embed-env.example/v1",
        embedding_api_key="embed-env-key",
        openai_base_url="https://legacy-env.example/v1",
        openai_api_key="legacy-env-key",
        chat_model="chat-env-model",
        embedding_model="embed-env-model",
    )

    resolved = resolve_provider_settings(
        settings,
        {
            "chat.base_url": "https://chat-db.example/v1",
            "chat.api_key": "chat-db-key",
            "chat.model": "chat-db-model",
            "embedding.base_url": "https://embed-db.example/v1",
            "embedding.api_key": "embed-db-key",
            "embedding.model": "embed-db-model",
        },
    )

    assert resolved.chat_base_url == "https://chat-db.example/v1"
    assert resolved.chat_api_key == "chat-db-key"
    assert resolved.chat_model == "chat-db-model"
    assert resolved.embedding_base_url == "https://embed-db.example/v1"
    assert resolved.embedding_api_key == "embed-db-key"
    assert resolved.embedding_model == "embed-db-model"


def test_legacy_stored_values_precede_provider_environment_values() -> None:
    settings = Settings(
        chat_base_url="https://chat-env.example/v1",
        chat_api_key="chat-env-key",
        embedding_base_url="https://embed-env.example/v1",
        embedding_api_key="embed-env-key",
        chat_model="chat-env-model",
        embedding_model="embed-env-model",
    )

    resolved = resolve_provider_settings(
        settings,
        {
            "base_url": "https://legacy-db.example/v1",
            "api_key": "legacy-db-key",
            "chat_model": "legacy-chat-model",
            "embedding_model": "legacy-embed-model",
        },
    )

    assert resolved.chat_base_url == "https://legacy-db.example/v1"
    assert resolved.chat_api_key == "legacy-db-key"
    assert resolved.chat_model == "legacy-chat-model"
    assert resolved.embedding_base_url == "https://legacy-db.example/v1"
    assert resolved.embedding_api_key == "legacy-db-key"
    assert resolved.embedding_model == "legacy-embed-model"


def test_resolution_combines_partial_values_field_by_field() -> None:
    settings = Settings(
        chat_base_url="https://chat-env.example/v1",
        chat_api_key="chat-env-key",
        embedding_base_url="",
        embedding_api_key="",
        openai_base_url="https://legacy-env.example/v1",
        openai_api_key="legacy-env-key",
        chat_model="chat-env-model",
        embedding_model="embed-env-model",
    )

    resolved = resolve_provider_settings(
        settings,
        {
            "chat.base_url": "https://chat-db.example/v1",
            "api_key": "legacy-db-key",
            "embedding_model": "legacy-embed-model",
        },
    )

    assert resolved.chat_base_url == "https://chat-db.example/v1"
    assert resolved.chat_api_key == "legacy-db-key"
    assert resolved.chat_model == "chat-env-model"
    assert resolved.embedding_base_url == "https://legacy-env.example/v1"
    assert resolved.embedding_api_key == "legacy-db-key"
    assert resolved.embedding_model == "legacy-embed-model"
