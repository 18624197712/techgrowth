import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .security import DeviceIdentity


class ConnectorRevokedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Pairing:
    device_id: str
    device_token: str


@dataclass(frozen=True, slots=True)
class ConnectionDiagnostic:
    ok: bool
    code: str
    message: str


def diagnose_server(
    base_url: str, *, http: httpx.Client | None = None, timeout: float = 12.0
) -> ConnectionDiagnostic:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ConnectionDiagnostic(False, "invalid_url", "服务器地址必须是有效的 HTTPS 地址")
    owned_client = http is None
    client = http or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = client.get(f"{base_url.rstrip('/')}/api/v1/health")
        body = response.text.casefold()
        if response.status_code == 403 and (
            "non-compliance icp filing" in body or response.headers.get("server") == "Beaver"
        ):
            return ConnectionDiagnostic(
                False, "icp_blocked", "阿里云备案接入拦截，请先完成域名备案接入后再配对"
            )
        if response.status_code != 200:
            return ConnectionDiagnostic(
                False, "http_error", f"服务器健康检查返回 HTTP {response.status_code}"
            )
        try:
            healthy = response.json().get("status") == "ok"
        except (ValueError, AttributeError):
            healthy = False
        if not healthy:
            return ConnectionDiagnostic(False, "unhealthy", "服务器健康检查响应无效")
        return ConnectionDiagnostic(True, "ok", "服务器连接正常")
    except httpx.TimeoutException:
        return ConnectionDiagnostic(False, "timeout", "连接服务器超时")
    except httpx.ConnectError as exc:
        detail = str(exc).casefold()
        if any(value in detail for value in ("eof", "reset", "ssl", "tls")):
            return ConnectionDiagnostic(
                False, "tls_connection_failed", "TLS 连接被中断，请检查域名证书和备案接入状态"
            )
        if any(value in detail for value in ("name", "dns", "getaddrinfo")):
            return ConnectionDiagnostic(False, "dns_failed", "域名 DNS 解析失败")
        return ConnectionDiagnostic(False, "connection_failed", "无法连接服务器")
    finally:
        if owned_client:
            client.close()


class ConnectorClient:
    def __init__(
        self,
        base_url: str,
        identity: DeviceIdentity,
        *,
        http: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("connector server must use HTTPS")
        self.base_url = base_url.rstrip("/")
        self.identity = identity
        self.http = http or httpx.Client(base_url=self.base_url, timeout=timeout)
        self.pairing: Pairing | None = None

    def pair(self, code: str, name: str) -> Pairing:
        response = self.http.post(
            "/api/v1/connector/pair",
            json={"code": code, "name": name, "public_key": self.identity.public_key_b64},
        )
        response.raise_for_status()
        payload = response.json()
        self.pairing = Pairing(payload["device_id"], payload["device_token"])
        return self.pairing

    def heartbeat(self, version: str) -> dict:
        return self._signed_json("POST", "/api/v1/connector/heartbeat", {"version": version})

    def jobs(self) -> list[dict]:
        return self._signed_request("GET", "/api/v1/connector/jobs").json()

    def register_repository(self, manifest: dict) -> dict:
        return self._signed_json("POST", "/api/v1/connector/repositories", manifest)

    def complete_job(self, job_id: str, result: dict) -> dict:
        return self._signed_json(
            "POST", f"/api/v1/connector/jobs/{job_id}/complete", {"result": result}
        )

    def upload_file(
        self,
        job_id: str,
        artifact_id: str,
        source: Path,
        relative_path: str,
        *,
        offset: int = 0,
        chunk_size: int = 256 * 1024,
        progress=None,
    ) -> dict:
        path = Path(source)
        size = path.stat().st_size
        if offset < 0 or offset > size:
            raise ValueError("upload offset is outside the file")
        endpoint = f"/api/v1/connector/uploads/{job_id}/{artifact_id}"
        current = offset
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
            stream.seek(offset)
            while current < size:
                chunk = stream.read(min(chunk_size, size - current))
                response = self._signed_request(
                    "PUT",
                    endpoint,
                    body=chunk,
                    params={"offset": current, "relative_path": relative_path},
                )
                received = int(response.json()["received"])
                if received <= current or received > size:
                    raise RuntimeError("server returned an invalid upload offset")
                current = received
                if progress:
                    progress(current, size)
        return self._signed_json(
            "POST",
            f"{endpoint}/complete",
            {"sha256": digest.hexdigest(), "size": size},
        )

    def close(self) -> None:
        self.http.close()

    def _signed_json(self, method: str, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return self._signed_request(method, path, body=body).json()

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        params: dict | None = None,
    ) -> httpx.Response:
        if self.pairing is None:
            raise RuntimeError("connector is not paired")
        headers = self.identity.signed_headers(method, path, body)
        headers.update(
            {
                "Authorization": f"Bearer {self.pairing.device_token}",
                "X-Device-Id": self.pairing.device_id,
                "Content-Type": "application/json"
                if method.upper() == "POST"
                else "application/octet-stream",
            }
        )
        response = self.http.request(method, path, content=body, params=params, headers=headers)
        if response.status_code == 401:
            raise ConnectorRevokedError("connector authorization was revoked")
        response.raise_for_status()
        return response
