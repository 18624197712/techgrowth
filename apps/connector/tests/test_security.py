import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from techgrowth_connector.security import CredentialStore, DeviceIdentity


class MemoryKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def test_device_signature_matches_server_canonical_request() -> None:
    identity = DeviceIdentity.generate()
    body = b'{"version":"0.1.0"}'
    headers = identity.signed_headers(
        "POST", "/api/v1/connector/heartbeat", body, timestamp=10, nonce="nonce-1"
    )
    digest = hashlib.sha256(body).hexdigest()
    canonical = f"POST\n/api/v1/connector/heartbeat\n10\nnonce-1\n{digest}".encode()

    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(identity.public_key_b64))
    public_key.verify(base64.b64decode(headers["X-Signature"]), canonical)


def test_credentials_round_trip_without_plaintext_config() -> None:
    backend = MemoryKeyring()
    store = CredentialStore(backend=backend)
    identity = DeviceIdentity.generate()

    store.save("device-1", "token-1", identity)
    loaded = store.load()

    assert loaded is not None
    assert loaded.device_id == "device-1"
    assert loaded.device_token == "token-1"
    assert loaded.identity.public_key_b64 == identity.public_key_b64
    assert "token-1" in backend.values.values()
