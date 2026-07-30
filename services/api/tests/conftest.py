from collections.abc import Generator
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

from techgrowth_api.config import Settings
from techgrowth_api.main import create_app
from techgrowth_api.services.auth import AuthService


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        secret_key="test-secret-key-that-is-long-enough",
        encryption_key="Z0FBQUFBQm5UZWNoR3Jvd3RoVGVzdEtleTEyMzQ1Njc4OTA=",
        secure_cookies=False,
        temp_upload_dir=tmp_path / "uploads",
    )


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient) -> tuple[TestClient, str]:
    auth: AuthService = client.app.state.services.auth
    auth.create_admin("developer@example.com", "correct horse battery staple")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "developer@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    setup = client.get("/api/v1/auth/totp/setup")
    secret = setup.json()["secret"]
    confirm = client.post("/api/v1/auth/totp/confirm", json={"code": pyotp.TOTP(secret).now()})
    assert confirm.status_code == 200
    return client, confirm.json()["csrf_token"]
