import base64
import json
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from techgrowth_api.domain.connector import canonical_request


def pair_device(authenticated_client):
    client, csrf = authenticated_client
    code = client.post("/api/v1/connectors/pairing-codes", headers={"X-CSRF-Token": csrf}).json()[
        "code"
    ]
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode()
    paired = client.post(
        "/api/v1/connector/pair",
        json={"code": code, "name": "Workstation", "public_key": public_key},
    ).json()
    return client, private_key, paired


def signed_headers(private_key, device, method: str, path: str, body: bytes, nonce: str):
    timestamp = int(time.time())
    signature = base64.b64encode(
        private_key.sign(canonical_request(method, path, timestamp, nonce, body))
    ).decode()
    return {
        "Authorization": f"Bearer {device['device_token']}",
        "X-Device-Id": device["device_id"],
        "X-Timestamp": str(timestamp),
        "X-Nonce": nonce,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }


def test_signed_heartbeat_rejects_replayed_nonce(authenticated_client) -> None:
    client, private_key, device = pair_device(authenticated_client)
    path = "/api/v1/connector/heartbeat"
    body = json.dumps({"version": "0.1.0"}, separators=(",", ":")).encode()
    headers = signed_headers(private_key, device, "POST", path, body, "same-nonce")

    first = client.post(path, content=body, headers=headers)
    replay = client.post(path, content=body, headers=headers)

    assert first.status_code == 200
    assert replay.status_code == 401


def test_revoked_device_cannot_poll_jobs(authenticated_client) -> None:
    client, private_key, device = pair_device(authenticated_client)
    _, csrf = authenticated_client
    revoked = client.delete(
        f"/api/v1/connectors/{device['device_id']}", headers={"X-CSRF-Token": csrf}
    )
    path = "/api/v1/connector/jobs"
    headers = signed_headers(private_key, device, "GET", path, b"", "jobs-nonce")

    assert revoked.status_code == 200
    assert client.get(path, headers=headers).status_code == 401


def test_completed_job_is_not_returned_again(authenticated_client) -> None:
    client, private_key, device = pair_device(authenticated_client)
    _, csrf = authenticated_client
    queued = client.post(
        f"/api/v1/connectors/{device['device_id']}/jobs",
        headers={"X-CSRF-Token": csrf},
        json={"kind": "upload_file", "payload": {}, "idempotency_key": "upload-once"},
    ).json()
    complete_path = f"/api/v1/connector/jobs/{queued['id']}/complete"
    complete_body = json.dumps(
        {"result": {"artifact_id": "artifact-1"}}, separators=(",", ":")
    ).encode()

    first = client.post(
        complete_path,
        content=complete_body,
        headers=signed_headers(
            private_key, device, "POST", complete_path, complete_body, "complete-1"
        ),
    )
    second = client.post(
        complete_path,
        content=complete_body,
        headers=signed_headers(
            private_key, device, "POST", complete_path, complete_body, "complete-2"
        ),
    )
    jobs_path = "/api/v1/connector/jobs"
    remaining = client.get(
        jobs_path,
        headers=signed_headers(private_key, device, "GET", jobs_path, b"", "jobs-after"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert remaining.json() == []
