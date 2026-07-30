import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def test_pairing_code_is_single_use(authenticated_client) -> None:
    client, csrf = authenticated_client
    pairing = client.post("/api/v1/connectors/pairing-codes", headers={"X-CSRF-Token": csrf}).json()
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode()

    first = client.post(
        "/api/v1/connector/pair",
        json={"code": pairing["code"], "name": "Workstation", "public_key": public_key},
    )
    second = client.post(
        "/api/v1/connector/pair",
        json={"code": pairing["code"], "name": "Other", "public_key": public_key},
    )

    assert first.status_code == 201
    assert first.json()["device_token"]
    assert second.status_code == 400
