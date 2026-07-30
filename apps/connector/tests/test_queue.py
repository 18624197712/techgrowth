from pathlib import Path

from techgrowth_connector.queue import OfflineQueue


def test_duplicate_idempotency_key_creates_one_queue_item(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue.db")

    first = queue.enqueue("repository.sync", {"path": "repo"}, "sync-1")
    second = queue.enqueue("repository.sync", {"path": "repo"}, "sync-1")

    assert first == second
    assert queue.pending_count() == 1


def test_failed_item_waits_for_backoff_then_can_resume(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue.db")
    item_id = queue.enqueue("upload", {"offset": 4}, "upload-1", now=100.0)
    item = queue.next_ready(now=100.0)
    assert item is not None and item.id == item_id

    queue.mark_failed(item_id, "offline", now=100.0)

    assert queue.next_ready(now=101.0) is None
    assert queue.next_ready(now=102.0).id == item_id
    queue.mark_complete(item_id)
    assert queue.pending_count() == 0


def test_queue_payload_can_persist_upload_offset(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue.db")
    item_id = queue.enqueue("server.job", {"offset": 0}, "job-1", now=100.0)

    queue.update_payload(item_id, {"offset": 4096})

    assert queue.next_ready(now=100.0).payload == {"offset": 4096}
