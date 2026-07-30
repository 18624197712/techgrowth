import hashlib
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from ..dependencies import connector_device, csrf_user, current_user
from ..models import ConnectorDeviceRecord, User
from ..schemas import (
    CompleteSyncJobRequest,
    PairConnectorRequest,
    RepositoryManifestRequest,
    SyncJobRequest,
    UploadCompleteRequest,
)

router = APIRouter(tags=["connector"])


class HeartbeatRequest(BaseModel):
    version: str


@router.post("/connectors/pairing-codes")
def create_pairing_code(request: Request, _: User = Depends(csrf_user)) -> dict:
    code, expires_at = request.app.state.services.connector.create_pairing_code()
    return {"code": code, "expires_at": expires_at}


@router.post("/connector/pair", status_code=status.HTTP_201_CREATED)
def pair(payload: PairConnectorRequest, request: Request) -> dict:
    try:
        device, raw_token = request.app.state.services.connector.pair(
            payload.code, payload.name, payload.public_key
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"device_id": device.id, "device_token": raw_token}


@router.post("/connector/heartbeat")
def heartbeat(
    payload: HeartbeatRequest, device: ConnectorDeviceRecord = Depends(connector_device)
) -> dict:
    return {"ok": True, "device_id": device.id, "version": payload.version}


@router.get("/connector/jobs")
def jobs(request: Request, device: ConnectorDeviceRecord = Depends(connector_device)) -> list[dict]:
    return [
        {
            "id": job.id,
            "kind": job.kind,
            "payload": job.payload,
            "idempotency_key": job.idempotency_key,
        }
        for job in request.app.state.services.connector.jobs(device.id)
    ]


@router.post("/connector/jobs/{job_id}/complete")
def complete_job(
    job_id: str,
    payload: CompleteSyncJobRequest,
    request: Request,
    device: ConnectorDeviceRecord = Depends(connector_device),
) -> dict:
    try:
        job = request.app.state.services.connector.complete_job(
            device.id, job_id, payload.result
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True, "job_id": job.id, "status": job.status}


@router.delete("/connectors/{device_id}")
def revoke_device(device_id: str, request: Request, _: User = Depends(csrf_user)) -> dict:
    try:
        request.app.state.services.connector.revoke(device_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True}


@router.post("/connector/repositories", status_code=status.HTTP_201_CREATED)
def register_repository(
    payload: RepositoryManifestRequest,
    request: Request,
    device: ConnectorDeviceRecord = Depends(connector_device),
) -> dict:
    try:
        item = request.app.state.services.connector.register_repository(device.id, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "id": item.id,
        "name": item.name,
        "languages": item.languages,
        "last_commit": item.last_commit,
        "last_synced_at": item.last_synced_at,
    }


@router.get("/repositories")
def list_repositories(request: Request, _: User = Depends(current_user)) -> list[dict]:
    return [
        {
            "id": item.id,
            "device_id": item.device_id,
            "name": item.name,
            "provider": item.provider,
            "languages": item.languages,
            "last_commit": item.last_commit,
            "last_synced_at": item.last_synced_at,
        }
        for item in request.app.state.services.connector.list_repositories()
    ]


@router.post("/connectors/{device_id}/jobs", status_code=status.HTTP_201_CREATED)
def queue_job(
    device_id: str,
    payload: SyncJobRequest,
    request: Request,
    _: User = Depends(csrf_user),
) -> dict:
    try:
        item = request.app.state.services.connector.queue_job(device_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "id": item.id,
        "kind": item.kind,
        "payload": item.payload,
        "status": item.status,
        "idempotency_key": item.idempotency_key,
    }


def safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise HTTPException(400, "relative_path is outside the repository")
    return str(path)


@router.put("/connector/uploads/{job_id}/{artifact_id}")
async def upload_chunk(
    job_id: str,
    artifact_id: str,
    request: Request,
    offset: int = Query(ge=0),
    relative_path: str = Query(min_length=1),
    device: ConnectorDeviceRecord = Depends(connector_device),
) -> dict:
    try:
        request.app.state.services.connector.require_job(device.id, job_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    content = await request.body()
    try:
        received = request.app.state.services.artifacts.append(artifact_id, offset, content)
        request.app.state.services.connector.record_upload(
            job_id,
            artifact_id,
            safe_relative_path(relative_path),
            str(request.app.state.settings.temp_upload_dir / f"{artifact_id}.enc"),
            received,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"artifact_id": artifact_id, "received": received}


@router.post("/connector/uploads/{job_id}/{artifact_id}/complete")
def complete_upload(
    job_id: str,
    artifact_id: str,
    payload: UploadCompleteRequest,
    request: Request,
    device: ConnectorDeviceRecord = Depends(connector_device),
) -> dict:
    try:
        request.app.state.services.connector.require_job(device.id, job_id)
        content = request.app.state.services.artifacts.read(artifact_id)
        digest = hashlib.sha256(content).hexdigest()
        if digest != payload.sha256 or len(content) != payload.size:
            raise ValueError("Upload digest or size does not match")
        item = request.app.state.services.connector.complete_upload(
            job_id, artifact_id, digest, len(content)
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"artifact_id": item.id, "sha256": item.sha256, "size": item.size}
