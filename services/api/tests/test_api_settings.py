def test_provider_setup_api_masks_api_key(authenticated_client) -> None:
    client, csrf = authenticated_client
    saved = client.put(
        "/api/v1/setup/provider",
        headers={"X-CSRF-Token": csrf},
        json={
            "chat": {
                "base_url": "https://chat.example/v1",
                "model": "chat-model",
                "api_key": "chat-secret-key",
            },
            "embedding": {
                "base_url": "https://embed.example/v1",
                "model": "embed-model",
                "api_key": "embed-secret-key",
            },
        },
    )
    status = client.get("/api/v1/setup").json()

    assert saved.status_code == 200
    assert status["provider"]["chat"]["api_key_configured"] is True
    assert status["provider"]["embedding"]["api_key_configured"] is True
    assert status["provider"]["chat"]["base_url"] == "https://chat.example/v1"
    assert status["provider"]["embedding"]["base_url"] == "https://embed.example/v1"
    assert "chat-secret-key" not in str(status)
    assert "embed-secret-key" not in str(status)


def test_provider_setup_rejects_missing_initial_key(authenticated_client) -> None:
    client, csrf = authenticated_client

    response = client.put(
        "/api/v1/setup/provider",
        headers={"X-CSRF-Token": csrf},
        json={
            "chat": {
                "base_url": "https://chat.example/v1",
                "model": "chat-model",
                "api_key": "",
            },
            "embedding": {
                "base_url": "https://embed.example/v1",
                "model": "embed-model",
                "api_key": "embed-secret-key",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "chat API key is required"


def test_notification_preferences_are_independently_configurable(authenticated_client) -> None:
    client, csrf = authenticated_client
    response = client.put(
        "/api/v1/notifications/preferences",
        headers={"X-CSRF-Token": csrf},
        json={
            "preferences": [
                {"channel": "email", "event": "daily_task", "enabled": True},
                {"channel": "web_push", "event": "daily_task", "enabled": False},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["enabled"] is True
    assert response.json()[1]["enabled"] is False


def test_setup_exposes_only_public_vapid_key(authenticated_client, settings) -> None:
    client, _ = authenticated_client
    settings.vapid_public_key = "public-vapid-key"
    settings.vapid_private_key = "private-vapid-key"

    status = client.get("/api/v1/setup").json()

    assert status["vapid_public_key"] == "public-vapid-key"
    assert "private-vapid-key" not in str(status)
