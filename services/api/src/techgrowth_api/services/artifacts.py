from datetime import UTC, datetime
from pathlib import Path

from ..crypto import SecretCipher


class TempArtifactStore:
    MAX_ARTIFACT_BYTES = 10 * 1024 * 1024

    def __init__(self, root: Path, cipher: SecretCipher) -> None:
        self.root = root
        self.cipher = cipher
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, artifact_id: str, offset: int, chunk: bytes) -> int:
        path = self._path(artifact_id)
        existing = self.read(artifact_id) if path.exists() else b""
        if offset != len(existing):
            raise ValueError(f"Expected offset {len(existing)}, got {offset}")
        combined = existing + chunk
        if len(combined) > self.MAX_ARTIFACT_BYTES:
            raise ValueError("Artifact exceeds 10 MiB limit")
        path.write_bytes(self.cipher.encrypt(base64_bytes(combined)).encode())
        return len(combined)

    def read(self, artifact_id: str) -> bytes:
        encrypted = self._path(artifact_id).read_text(encoding="utf-8")
        return unbase64_bytes(self.cipher.decrypt(encrypted))

    def delete(self, artifact_id: str) -> None:
        self._path(artifact_id).unlink(missing_ok=True)

    def cleanup(self, expirations: dict[str, datetime]) -> list[str]:
        now = datetime.now(UTC)
        removed: list[str] = []
        for artifact_id, expires_at in expirations.items():
            aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
            if aware <= now and self._path(artifact_id).exists():
                self.delete(artifact_id)
                removed.append(artifact_id)
        return removed

    def _path(self, artifact_id: str) -> Path:
        if not artifact_id or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for char in artifact_id
        ):
            raise ValueError("Artifact id contains invalid characters")
        return self.root / f"{artifact_id}.enc"


def base64_bytes(value: bytes) -> str:
    import base64

    return base64.b64encode(value).decode()


def unbase64_bytes(value: str) -> bytes:
    import base64

    return base64.b64decode(value)
