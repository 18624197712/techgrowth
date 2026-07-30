import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical_request(method: str, path: str, timestamp: int, nonce: str, body: bytes) -> bytes:
    digest = hashlib.sha256(body).hexdigest()
    return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{digest}".encode()


def verify_connector_signature(
    public_key: Ed25519PublicKey,
    signature: str,
    method: str,
    path: str,
    timestamp: int,
    nonce: str,
    body: bytes,
) -> bool:
    try:
        public_key.verify(
            base64.b64decode(signature),
            canonical_request(method, path, timestamp, nonce, body),
        )
    except (InvalidSignature, ValueError):
        return False
    return True
