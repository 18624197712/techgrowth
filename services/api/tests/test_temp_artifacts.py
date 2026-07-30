from datetime import UTC, datetime, timedelta
from pathlib import Path

from techgrowth_api.crypto import SecretCipher
from techgrowth_api.services.artifacts import TempArtifactStore


def test_temp_artifact_is_encrypted_and_can_resume_by_offset(tmp_path: Path) -> None:
    store = TempArtifactStore(tmp_path, SecretCipher("installation-secret"))

    assert store.append("artifact-1", 0, b"print('secret')") == 15
    assert store.append("artifact-1", 15, b"\n# tests") == 23

    encrypted = (tmp_path / "artifact-1.enc").read_bytes()
    assert b"print('secret')" not in encrypted
    assert store.read("artifact-1") == b"print('secret')\n# tests"


def test_cleanup_removes_expired_artifacts(tmp_path: Path) -> None:
    store = TempArtifactStore(tmp_path, SecretCipher("installation-secret"))
    store.append("expired", 0, b"content")

    removed = store.cleanup({"expired": datetime.now(UTC) - timedelta(seconds=1)})

    assert removed == ["expired"]
    assert not (tmp_path / "expired.enc").exists()
