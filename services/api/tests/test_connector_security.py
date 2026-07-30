import base64
import hashlib
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from techgrowth_api.domain.connector import canonical_request, verify_connector_signature


def test_connector_signature_covers_method_path_time_nonce_and_body() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    body = b'{"state":"ready"}'
    timestamp = int(time.time())
    message = canonical_request("POST", "/connector/v1/heartbeat", timestamp, "n-1", body)
    signature = base64.b64encode(private_key.sign(message)).decode()

    assert verify_connector_signature(
        public_key, signature, "POST", "/connector/v1/heartbeat", timestamp, "n-1", body
    )
    assert not verify_connector_signature(
        public_key, signature, "POST", "/connector/v1/heartbeat", timestamp, "n-1", body + b"x"
    )


def test_canonical_request_includes_sha256_body_digest() -> None:
    message = canonical_request("PUT", "/upload", 10, "abc", b"payload").decode()
    assert hashlib.sha256(b"payload").hexdigest() in message
