from dataclasses import dataclass
from pathlib import Path

from .client import ConnectorClient, Pairing
from .config import ConnectorConfig
from .queue import OfflineQueue
from .runtime import ConnectorRuntime
from .security import CredentialStore, DeviceIdentity


@dataclass(slots=True)
class ConnectorServices:
    config: ConnectorConfig
    queue: OfflineQueue
    credentials: CredentialStore
    runtime: ConnectorRuntime
    client_factory: type[ConnectorClient]

    @classmethod
    def load(
        cls,
        data_dir: Path,
        *,
        credential_store: CredentialStore | None = None,
        client_factory: type[ConnectorClient] = ConnectorClient,
    ) -> "ConnectorServices":
        root = Path(data_dir)
        root.mkdir(parents=True, exist_ok=True)
        config = ConnectorConfig.load(root / "connector.json")
        queue = OfflineQueue(root / "queue.db")
        credentials = credential_store or CredentialStore()
        runtime = ConnectorRuntime(config, queue)
        stored = credentials.load()
        if stored and config.server_url:
            client = client_factory(config.server_url, stored.identity)
            client.pairing = Pairing(stored.device_id, stored.device_token)
            runtime.client = client
        return cls(config, queue, credentials, runtime, client_factory)

    def pair(self, server_url: str, code: str, device_name: str) -> Pairing:
        identity = DeviceIdentity.generate()
        client = self.client_factory(server_url, identity)
        pairing = client.pair(code, device_name)
        self.credentials.save(pairing.device_id, pairing.device_token, identity)
        if self.runtime.client is not None:
            self.runtime.client.close()
        self.config.server_url = server_url.rstrip("/")
        self.config.device_name = device_name
        self.config.save()
        self.runtime.client = client
        return pairing

    def clear_pairing(self) -> None:
        if self.runtime.client is not None:
            self.runtime.client.close()
        self.runtime.client = None
        self.credentials.clear()

