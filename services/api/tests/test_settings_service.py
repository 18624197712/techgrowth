from techgrowth_api.services.settings import ProviderSettings, SettingsService


def test_provider_secrets_are_encrypted_and_masked(client) -> None:
    service = SettingsService(
        client.app.state.database.session_factory,
        client.app.state.services.auth.cipher,
    )
    service.save_provider(
        ProviderSettings(
            base_url="https://model.example/v1",
            chat_model="chat-model",
            embedding_model="embed-model",
            api_key="top-secret-key",
        )
    )

    public = service.provider_status()
    raw_database = str(
        client.app.state.database.engine.raw_connection()
        .cursor()
        .execute("select value_enc from app_settings where key = 'provider.api_key'")
        .fetchone()
    )

    assert public["api_key_configured"] is True
    assert "top-secret-key" not in raw_database
