import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from techgrowth_connector.client import ConnectorClient, Pairing
from techgrowth_connector.security import DeviceIdentity


def verify_signature(request: httpx.Request, identity: DeviceIdentity) -> None:
    timestamp = request.headers["X-Timestamp"]
    nonce = request.headers["X-Nonce"]
    digest = hashlib.sha256(request.content).hexdigest()
    canonical = f"{request.method}\n{request.url.path}\n{timestamp}\n{nonce}\n{digest}".encode()
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(identity.public_key_b64))
    key.verify(base64.b64decode(request.headers["X-Signature"]), canonical)


def test_non_local_connector_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        ConnectorClient("http://example.com", DeviceIdentity.generate())


def test_signed_heartbeat_uses_device_token_and_signature() -> None:
    identity = DeviceIdentity.generate()

    def handler(request: httpx.Request) -> httpx.Response:
        verify_signature(request, identity)
        assert request.headers["Authorization"] == "Bearer token-1"
        assert request.headers["X-Device-Id"] == "device-1"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="https://growth.example.com")
    client = ConnectorClient("https://growth.example.com", identity, http=http)
    client.pairing = Pairing("device-1", "token-1")

    assert client.heartbeat("0.1.0")["ok"] is True


def test_completed_job_is_acknowledged_with_signed_result() -> None:
    identity = DeviceIdentity.generate()

    def handler(request: httpx.Request) -> httpx.Response:
        verify_signature(request, identity)
        assert request.url.path == "/api/v1/connector/jobs/job-1/complete"
        assert json.loads(request.content) == {"result": {"artifact_id": "artifact-1"}}
        return httpx.Response(200, json={"ok": True})

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://growth.example.com"
    )
    client = ConnectorClient("https://growth.example.com", identity, http=http)
    client.pairing = Pairing("device-1", "token-1")

    assert client.complete_job("job-1", {"artifact_id": "artifact-1"})["ok"] is True


def test_upload_resumes_from_saved_offset_and_completes_digest(tmp_path: Path) -> None:
    identity = DeviceIdentity.generate()
    content = b"0123456789"
    source = tmp_path / "main.py"
    source.write_bytes(content)
    received = bytearray(content[:4])

    def handler(request: httpx.Request) -> httpx.Response:
        verify_signature(request, identity)
        if request.method == "PUT":
            query = parse_qs(request.url.query.decode())
            assert int(query["offset"][0]) == len(received)
            received.extend(request.content)
            return httpx.Response(200, json={"received": len(received)})
        payload = json.loads(request.content)
        assert payload == {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        return httpx.Response(200, json={"artifact_id": "artifact-1"})

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://growth.example.com"
    )
    client = ConnectorClient("https://growth.example.com", identity, http=http)
    client.pairing = Pairing("device-1", "token-1")

    result = client.upload_file(
        "job-1", "artifact-1", source, "src/main.py", offset=4, chunk_size=3
    )

    assert bytes(received) == content
    assert result["artifact_id"] == "artifact-1"
