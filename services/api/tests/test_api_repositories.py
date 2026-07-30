import hashlib
import json

from tests.test_connector_routes import pair_device, signed_headers


def test_connector_registers_repository_and_receives_admin_job(authenticated_client) -> None:
    client, private_key, device = pair_device(authenticated_client)
    _, csrf = authenticated_client
    path = "/api/v1/connector/repositories"
    body = json.dumps(
        {
            "external_key": "local:agent-lab",
            "name": "agent-lab",
            "default_branch": "main",
            "languages": {"Python": 92, "Shell": 8},
            "last_commit": "abc123",
        },
        separators=(",", ":"),
    ).encode()
    response = client.post(
        path,
        content=body,
        headers=signed_headers(private_key, device, "POST", path, body, "repo-1"),
    )
    queued = client.post(
        f"/api/v1/connectors/{device['device_id']}/jobs",
        headers={"X-CSRF-Token": csrf},
        json={
            "kind": "upload_files",
            "payload": {"repository_id": response.json()["id"], "paths": ["src/main.py"]},
            "idempotency_key": "analyze-agent-lab-1",
        },
    )
    jobs_path = "/api/v1/connector/jobs"
    jobs = client.get(
        jobs_path,
        headers=signed_headers(private_key, device, "GET", jobs_path, b"", "jobs-2"),
    )

    assert response.status_code == 201
    assert queued.status_code == 201
    assert jobs.json()[0]["id"] == queued.json()["id"]
    assert client.get("/api/v1/repositories").json()[0]["name"] == "agent-lab"


def test_connector_upload_is_encrypted_and_hash_verified(authenticated_client) -> None:
    client, private_key, device = pair_device(authenticated_client)
    _, csrf = authenticated_client
    queued = client.post(
        f"/api/v1/connectors/{device['device_id']}/jobs",
        headers={"X-CSRF-Token": csrf},
        json={
            "kind": "upload_files",
            "payload": {"paths": ["src/main.py"]},
            "idempotency_key": "upload-1",
        },
    ).json()
    content = b"print('hello')\n"
    path = f"/api/v1/connector/uploads/{queued['id']}/artifact-1"
    uploaded = client.put(
        path + "?offset=0&relative_path=src%2Fmain.py",
        content=content,
        headers=signed_headers(private_key, device, "PUT", path, content, "upload-nonce"),
    )
    complete_path = path + "/complete"
    complete_body = json.dumps(
        {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)},
        separators=(",", ":"),
    ).encode()
    completed = client.post(
        complete_path,
        content=complete_body,
        headers=signed_headers(
            private_key, device, "POST", complete_path, complete_body, "complete-nonce"
        ),
    )

    assert uploaded.json()["received"] == len(content)
    assert completed.status_code == 200
    assert completed.json()["sha256"] == hashlib.sha256(content).hexdigest()
