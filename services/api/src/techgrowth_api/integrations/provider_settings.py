from ..config import Settings


def resolve_provider_settings(settings: Settings, stored: dict[str, str]) -> Settings:
    legacy_base_url = stored.get("base_url", "")
    legacy_api_key = stored.get("api_key", "")
    return settings.model_copy(
        update={
            "chat_base_url": stored.get("chat.base_url")
            or legacy_base_url
            or settings.chat_base_url
            or settings.openai_base_url,
            "chat_api_key": stored.get("chat.api_key")
            or legacy_api_key
            or settings.chat_api_key
            or settings.openai_api_key,
            "chat_model": stored.get("chat.model")
            or stored.get("chat_model")
            or settings.chat_model,
            "embedding_base_url": stored.get("embedding.base_url")
            or legacy_base_url
            or settings.embedding_base_url
            or settings.openai_base_url,
            "embedding_api_key": stored.get("embedding.api_key")
            or legacy_api_key
            or settings.embedding_api_key
            or settings.openai_api_key,
            "embedding_model": stored.get("embedding.model")
            or stored.get("embedding_model")
            or settings.embedding_model,
        }
    )
