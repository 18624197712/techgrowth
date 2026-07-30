import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class KeyringBackend(Protocol):
    def set_password(self, service: str, username: str, password: str) -> None: ...

    def get_password(self, service: str, username: str) -> str | None: ...

    def delete_password(self, service: str, username: str) -> None: ...


def canonical_request(method: str, path: str, timestamp: int, nonce: str, body: bytes) -> bytes:
    digest = hashlib.sha256(body).hexdigest()
    return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{digest}".encode()


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls) -> "DeviceIdentity":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_key_b64(cls, value: str) -> "DeviceIdentity":
        return cls(Ed25519PrivateKey.from_private_bytes(base64.b64decode(value)))

    @property
    def private_key_b64(self) -> str:
        raw = self.private_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        return base64.b64encode(raw).decode()

    @property
    def public_key_b64(self) -> str:
        raw = self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw).decode()

    def signed_headers(
        self,
        method: str,
        path: str,
        body: bytes,
        *,
        timestamp: int | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        request_time = timestamp if timestamp is not None else int(time.time())
        request_nonce = nonce or secrets.token_urlsafe(18)
        signature = self.private_key.sign(
            canonical_request(method, path, request_time, request_nonce, body)
        )
        return {
            "X-Timestamp": str(request_time),
            "X-Nonce": request_nonce,
            "X-Signature": base64.b64encode(signature).decode(),
        }


@dataclass(frozen=True, slots=True)
class StoredCredentials:
    device_id: str
    device_token: str
    identity: DeviceIdentity


class CredentialStore:
    SERVICE = "TechGrowth Connector"

    def __init__(self, backend: KeyringBackend | None = None) -> None:
        if backend is None:
            import keyring

            backend = keyring
        self.backend = backend

    def save(self, device_id: str, device_token: str, identity: DeviceIdentity) -> None:
        self.backend.set_password(self.SERVICE, "device_id", device_id)
        self.backend.set_password(self.SERVICE, "device_token", device_token)
        self.backend.set_password(self.SERVICE, "private_key", identity.private_key_b64)

    def load(self) -> StoredCredentials | None:
        device_id = self.backend.get_password(self.SERVICE, "device_id")
        device_token = self.backend.get_password(self.SERVICE, "device_token")
        private_key = self.backend.get_password(self.SERVICE, "private_key")
        if not device_id or not device_token or not private_key:
            return None
        return StoredCredentials(
            device_id=device_id,
            device_token=device_token,
            identity=DeviceIdentity.from_private_key_b64(private_key),
        )

    def clear(self) -> None:
        for username in ("device_id", "device_token", "private_key"):
            try:
                self.backend.delete_password(self.SERVICE, username)
            except Exception:
                pass
