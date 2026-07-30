from pathlib import Path

import httpx

from . import __version__
from .client import ConnectorClient, ConnectorRevokedError
from .config import ConnectorConfig
from .queue import OfflineQueue, QueueItem
from .repository import build_manifest
from .scanner import RepositoryScanner, UnsafePathError


class ConnectorRuntime:
    def __init__(
        self,
        config: ConnectorConfig,
        queue: OfflineQueue,
        *,
        client: ConnectorClient | None = None,
    ) -> None:
        self.config = config
        self.queue = queue
        self.client = client

    def sync_repositories(self, *, now: float | None = None) -> list[dict]:
        if not self.config.authorized_roots:
            return []
        scanner = self._scanner()
        manifests: list[dict] = []
        for repository in scanner.discover_repositories():
            files = scanner.list_shareable_files(repository)
            manifest = build_manifest(repository, files)
            manifests.append(manifest)
            self.config.repositories[manifest["external_key"]] = str(repository)
            if self.client is None:
                self._queue_manifest(manifest, now)
                continue
            try:
                self.client.register_repository(manifest)
            except (httpx.HTTPError, OSError):
                self._queue_manifest(manifest, now)
        self.config.save()
        return manifests

    def poll_once(self, *, now: float | None = None) -> None:
        client = self._client()
        client.heartbeat(__version__)
        for job in client.jobs():
            payload = {
                "job_id": job["id"],
                "job_kind": job["kind"],
                "job_payload": job.get("payload", {}),
                "offset": 0,
            }
            self.queue.enqueue("server.job", payload, job["idempotency_key"], now=now)
        self.process_queue(now=now)

    def process_queue(self, *, now: float | None = None, max_items: int = 25) -> None:
        for _ in range(max_items):
            item = self.queue.next_ready(now=now)
            if item is None:
                return
            try:
                if item.kind == "repository.sync":
                    self._client().register_repository(item.payload["manifest"])
                elif item.kind == "server.job":
                    self._process_server_job(item)
                else:
                    raise ValueError(f"unsupported queue item: {item.kind}")
            except ConnectorRevokedError:
                raise
            except (httpx.HTTPError, OSError, RuntimeError, UnsafePathError, ValueError) as exc:
                self.queue.mark_failed(item.id, str(exc), now=now)
                return
            self.queue.mark_complete(item.id)

    def _process_server_job(self, item: QueueItem) -> None:
        payload = item.payload
        if payload["job_kind"] != "upload_file":
            raise ValueError(f"unsupported server job: {payload['job_kind']}")
        job_payload = payload["job_payload"]
        repository_value = self.config.repositories.get(job_payload["external_key"])
        if not repository_value:
            raise UnsafePathError("server requested an unknown repository")
        scanner = self._scanner()
        repository = scanner.require_authorized(Path(repository_value))
        source = scanner.require_authorized(repository / job_payload["relative_path"])
        if not source.is_relative_to(repository):
            raise UnsafePathError("requested file is outside the repository")
        if source not in set(scanner.list_shareable_files(repository)):
            raise UnsafePathError("requested file is excluded from sharing")

        def save_progress(received: int, _: int) -> None:
            updated = dict(item.payload)
            updated["offset"] = received
            self.queue.update_payload(item.id, updated)

        result = self._client().upload_file(
            payload["job_id"],
            job_payload["artifact_id"],
            source,
            job_payload["relative_path"],
            offset=int(payload.get("offset", 0)),
            progress=save_progress,
        )
        self._client().complete_job(payload["job_id"], result)

    def _queue_manifest(self, manifest: dict, now: float | None) -> None:
        self.queue.enqueue(
            "repository.sync",
            {"manifest": manifest},
            f"repository:{manifest['external_key']}:{manifest['last_commit']}",
            now=now,
        )

    def _scanner(self) -> RepositoryScanner:
        return RepositoryScanner([Path(item) for item in self.config.authorized_roots])

    def _client(self) -> ConnectorClient:
        if self.client is None:
            raise RuntimeError("connector is not paired")
        return self.client

