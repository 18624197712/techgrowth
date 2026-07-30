import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QueueItem:
    id: str
    kind: str
    payload: dict
    idempotency_key: str
    attempts: int
    available_at: float
    last_error: str


class OfflineQueue:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_items (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at REAL NOT NULL,
                    last_error TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def enqueue(
        self, kind: str, payload: dict, idempotency_key: str, *, now: float | None = None
    ) -> str:
        item_id = str(uuid.uuid4())
        available_at = time.time() if now is None else now
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO queue_items
                (id, kind, payload, idempotency_key, status, available_at)
                VALUES (?, ?, ?, ?, 'queued', ?)
                """,
                (item_id, kind, serialized, idempotency_key, available_at),
            )
            row = db.execute(
                "SELECT id FROM queue_items WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        return str(row[0])

    def next_ready(self, *, now: float | None = None) -> QueueItem | None:
        current = time.time() if now is None else now
        with self._connect() as db:
            row = db.execute(
                """
                SELECT id, kind, payload, idempotency_key, attempts, available_at, last_error
                FROM queue_items
                WHERE status IN ('queued', 'failed') AND available_at <= ?
                ORDER BY available_at, rowid
                LIMIT 1
                """,
                (current,),
            ).fetchone()
        if not row:
            return None
        return QueueItem(
            id=row[0],
            kind=row[1],
            payload=json.loads(row[2]),
            idempotency_key=row[3],
            attempts=row[4],
            available_at=row[5],
            last_error=row[6],
        )

    def mark_failed(self, item_id: str, error: str, *, now: float | None = None) -> None:
        current = time.time() if now is None else now
        with self._connect() as db:
            row = db.execute(
                "SELECT attempts FROM queue_items WHERE id = ?", (item_id,)
            ).fetchone()
            if not row:
                return
            attempts = int(row[0]) + 1
            delay = min(300, 2**attempts)
            db.execute(
                """
                UPDATE queue_items
                SET status = 'failed', attempts = ?, available_at = ?, last_error = ?
                WHERE id = ?
                """,
                (attempts, current + delay, error[:500], item_id),
            )

    def mark_complete(self, item_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM queue_items WHERE id = ?", (item_id,))

    def update_payload(self, item_id: str, payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute("UPDATE queue_items SET payload = ? WHERE id = ?", (serialized, item_id))

    def pending_count(self) -> int:
        with self._connect() as db:
            row = db.execute("SELECT COUNT(*) FROM queue_items").fetchone()
        return int(row[0])

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
