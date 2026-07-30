from pathlib import Path

import httpx

from techgrowth_connector.config import ConnectorConfig
from techgrowth_connector.queue import OfflineQueue
from techgrowth_connector.runtime import ConnectorRuntime


class FakeClient:
    def __init__(self) -> None:
        self.registered: list[dict] = []
        self.server_jobs: list[dict] = []
        self.upload_offsets: list[int] = []
        self.completed: list[tuple[str, dict]] = []
        self.fail_upload = False

    def heartbeat(self, version: str) -> dict:
        return {"ok": True, "version": version}

    def jobs(self) -> list[dict]:
        jobs, self.server_jobs = self.server_jobs, []
        return jobs

    def register_repository(self, manifest: dict) -> dict:
        self.registered.append(manifest)
        return manifest

    def upload_file(
        self,
        job_id: str,
        artifact_id: str,
        source: Path,
        relative_path: str,
        *,
        offset: int,
        progress,
    ) -> dict:
        self.upload_offsets.append(offset)
        if self.fail_upload:
            progress(4, source.stat().st_size)
            raise httpx.ConnectError("offline")
        progress(source.stat().st_size, source.stat().st_size)
        return {"artifact_id": artifact_id}

    def complete_job(self, job_id: str, result: dict) -> dict:
        self.completed.append((job_id, result))
        return {"ok": True}


def make_repository(path: Path) -> Path:
    refs = path / ".git" / "refs" / "heads"
    refs.mkdir(parents=True)
    (path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (refs / "main").write_text("abc123\n", encoding="utf-8")
    (path / "main.py").write_text("print('ready')", encoding="utf-8")
    return path


def test_config_file_contains_no_device_credentials(tmp_path: Path) -> None:
    path = tmp_path / "connector.json"
    config = ConnectorConfig(path=path, server_url="https://growth.example.com")
    config.authorized_roots = [str(tmp_path / "projects")]
    config.save()

    raw = path.read_text(encoding="utf-8")

    assert "device_token" not in raw
    assert "private_key" not in raw
    assert ConnectorConfig.load(path).server_url == "https://growth.example.com"


def test_repository_sync_registers_manifest_and_local_mapping(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo = make_repository(root / "product")
    config = ConnectorConfig(path=tmp_path / "connector.json", authorized_roots=[str(root)])
    client = FakeClient()
    runtime = ConnectorRuntime(config, OfflineQueue(tmp_path / "queue.db"), client=client)

    runtime.sync_repositories()

    assert client.registered[0]["last_commit"] == "abc123"
    external_key = client.registered[0]["external_key"]
    assert config.repositories[external_key] == str(repo.resolve())


def test_upload_job_resumes_from_persisted_offset_after_disconnect(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    make_repository(root / "product")
    config = ConnectorConfig(path=tmp_path / "connector.json", authorized_roots=[str(root)])
    client = FakeClient()
    runtime = ConnectorRuntime(config, OfflineQueue(tmp_path / "queue.db"), client=client)
    runtime.sync_repositories()
    external_key = next(iter(config.repositories))
    client.server_jobs = [
        {
            "id": "job-1",
            "kind": "upload_file",
            "idempotency_key": "upload-1",
            "payload": {
                "external_key": external_key,
                "relative_path": "main.py",
                "artifact_id": "artifact-1",
            },
        }
    ]
    client.fail_upload = True

    runtime.poll_once(now=100.0)
    queued = runtime.queue.next_ready(now=102.0)
    assert queued is not None
    assert queued.payload["offset"] == 4

    client.fail_upload = False
    runtime.process_queue(now=102.0)

    assert client.upload_offsets == [0, 4]
    assert client.completed == [("job-1", {"artifact_id": "artifact-1"})]
    assert runtime.queue.pending_count() == 0
