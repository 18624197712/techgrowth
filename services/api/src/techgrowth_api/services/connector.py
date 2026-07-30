import base64
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..crypto import constant_time_matches, token_hash
from ..domain.connector import verify_connector_signature
from ..models import (
    ConnectorDeviceRecord,
    ConnectorNonceRecord,
    PairingCodeRecord,
    RepositoryRecord,
    SyncJobRecord,
    UploadArtifactRecord,
)
from ..schemas import RepositoryManifestRequest, SyncJobRequest


class ConnectorService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def create_pairing_code(self) -> tuple[str, datetime]:
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        with self.session_factory() as db:
            db.add(PairingCodeRecord(code_hash=token_hash(code), expires_at=expires_at))
            db.commit()
        return code, expires_at

    def pair(self, code: str, name: str, public_key: str) -> tuple[ConnectorDeviceRecord, str]:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            pairing = db.scalar(
                select(PairingCodeRecord).where(PairingCodeRecord.code_hash == token_hash(code))
            )
            if not pairing or pairing.used_at is not None or self._aware(pairing.expires_at) <= now:
                raise ValueError("Pairing code is invalid or expired")
            raw_token = secrets.token_urlsafe(48)
            device = ConnectorDeviceRecord(
                name=name, public_key=public_key, token_hash=token_hash(raw_token)
            )
            pairing.used_at = now
            db.add(device)
            db.commit()
            return device, raw_token

    def authenticate(
        self,
        device_id: str,
        raw_token: str,
        method: str,
        path: str,
        timestamp: int,
        nonce: str,
        signature: str,
        body: bytes,
    ) -> ConnectorDeviceRecord:
        now = datetime.now(UTC)
        if abs(now.timestamp() - timestamp) > 300:
            raise ValueError("Signed request timestamp is outside the allowed window")
        with self.session_factory() as db:
            device = db.get(ConnectorDeviceRecord, device_id)
            if (
                not device
                or device.revoked_at is not None
                or not constant_time_matches(raw_token, device.token_hash)
            ):
                raise ValueError("Connector authentication failed")
            try:
                public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(device.public_key))
            except ValueError as exc:
                raise ValueError("Connector public key is invalid") from exc
            if not verify_connector_signature(
                public_key, signature, method, path, timestamp, nonce, body
            ):
                raise ValueError("Connector signature is invalid")
            db.add(ConnectorNonceRecord(nonce=nonce, device_id=device.id))
            try:
                device.last_seen_at = now
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise ValueError("Connector nonce was already used") from exc
            db.expunge(device)
            return device

    def revoke(self, device_id: str) -> None:
        with self.session_factory() as db:
            device = db.get(ConnectorDeviceRecord, device_id)
            if not device:
                raise LookupError("Connector device not found")
            device.revoked_at = datetime.now(UTC)
            db.commit()

    def jobs(self, device_id: str) -> list[SyncJobRecord]:
        with self.session_factory() as db:
            return list(
                db.scalars(
                    select(SyncJobRecord).where(
                        SyncJobRecord.device_id == device_id,
                        SyncJobRecord.status == "queued",
                    )
                ).all()
            )

    def register_repository(
        self, device_id: str, manifest: RepositoryManifestRequest
    ) -> RepositoryRecord:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            repository = db.scalar(
                select(RepositoryRecord).where(
                    RepositoryRecord.external_key == manifest.external_key
                )
            )
            values = manifest.model_dump()
            if repository:
                if repository.device_id != device_id:
                    raise ValueError("Repository belongs to another connector")
                for key, value in values.items():
                    setattr(repository, key, value)
            else:
                repository = RepositoryRecord(device_id=device_id, **values)
                db.add(repository)
            repository.last_synced_at = now
            db.commit()
            return repository

    def list_repositories(self) -> list[RepositoryRecord]:
        with self.session_factory() as db:
            return list(
                db.scalars(
                    select(RepositoryRecord).order_by(RepositoryRecord.last_synced_at.desc())
                ).all()
            )

    def queue_job(self, device_id: str, request: SyncJobRequest) -> SyncJobRecord:
        with self.session_factory() as db:
            device = db.get(ConnectorDeviceRecord, device_id)
            if not device or device.revoked_at is not None:
                raise LookupError("Connector device not found")
            existing = db.scalar(
                select(SyncJobRecord).where(
                    SyncJobRecord.idempotency_key == request.idempotency_key
                )
            )
            if existing:
                return existing
            job = SyncJobRecord(device_id=device_id, **request.model_dump())
            db.add(job)
            db.commit()
            return job

    def require_job(self, device_id: str, job_id: str) -> SyncJobRecord:
        with self.session_factory() as db:
            job = db.get(SyncJobRecord, job_id)
            if not job or job.device_id != device_id:
                raise LookupError("Sync job not found")
            db.expunge(job)
            return job

    def complete_job(self, device_id: str, job_id: str, result: dict) -> SyncJobRecord:
        with self.session_factory() as db:
            job = db.get(SyncJobRecord, job_id)
            if not job or job.device_id != device_id:
                raise LookupError("Sync job not found")
            if job.status != "completed":
                job.status = "completed"
                job.result = result
                job.completed_at = datetime.now(UTC)
                db.commit()
            db.expunge(job)
            return job

    def record_upload(
        self,
        job_id: str,
        artifact_id: str,
        relative_path: str,
        encrypted_path: str,
        size: int,
    ) -> UploadArtifactRecord:
        with self.session_factory() as db:
            item = db.get(UploadArtifactRecord, artifact_id)
            if item and item.job_id != job_id:
                raise ValueError("Artifact belongs to another job")
            if not item:
                item = UploadArtifactRecord(
                    id=artifact_id,
                    job_id=job_id,
                    relative_path=relative_path,
                    encrypted_path=encrypted_path,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
                db.add(item)
            item.size = size
            db.commit()
            return item

    def complete_upload(
        self, job_id: str, artifact_id: str, sha256: str, size: int
    ) -> UploadArtifactRecord:
        with self.session_factory() as db:
            item = db.get(UploadArtifactRecord, artifact_id)
            if not item or item.job_id != job_id:
                raise LookupError("Upload artifact not found")
            item.sha256 = sha256
            item.size = size
            db.commit()
            return item

    def expired_artifacts(self) -> dict[str, datetime]:
        with self.session_factory() as db:
            items = db.scalars(select(UploadArtifactRecord)).all()
            return {item.id: self._aware(item.expires_at) for item in items}

    def remove_artifacts(self, artifact_ids: list[str]) -> None:
        if not artifact_ids:
            return
        with self.session_factory() as db:
            for artifact_id in artifact_ids:
                item = db.get(UploadArtifactRecord, artifact_id)
                if item:
                    db.delete(item)
            db.commit()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)
