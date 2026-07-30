import pyotp
from fastapi.testclient import TestClient

from techgrowth_api.services.auth import AuthService


def test_health_is_available_without_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_first_login_requires_totp_enrollment(client: TestClient) -> None:
    auth: AuthService = client.app.state.services.auth
    auth.create_admin("developer@example.com", "correct horse battery staple")

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "developer@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["next"] == "totp_setup"

    setup = client.get("/api/v1/auth/totp/setup")
    code = pyotp.TOTP(setup.json()["secret"]).now()
    confirmed = client.post("/api/v1/auth/totp/confirm", json={"code": code})

    assert confirmed.status_code == 200
    assert confirmed.json()["csrf_token"]
    assert len(confirmed.json()["recovery_codes"]) == 8
    assert client.get("/api/v1/auth/me").json()["email"] == "developer@example.com"


def test_authenticated_mutation_rejects_missing_csrf(authenticated_client) -> None:
    client, _ = authenticated_client
    response = client.post("/api/v1/connectors/pairing-codes")
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token invalid"
