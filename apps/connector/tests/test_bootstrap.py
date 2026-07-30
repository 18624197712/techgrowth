from pathlib import Path

from techgrowth_connector.bootstrap import ConnectorServices
from techgrowth_connector.client import Pairing
from techgrowth_connector.security import StoredCredentials


class MemoryCredentials:
    def __init__(self) -> None:
        self.value: StoredCredentials | None = None
        self.cleared = False

    def load(self) -> StoredCredentials | None:
        return self.value

    def save(self, device_id, device_token, identity) -> None:
        self.value = StoredCredentials(device_id, device_token, identity)

    def clear(self) -> None:
        self.value = None
        self.cleared = True


class FakePairClient:
    def __init__(self, base_url, identity) -> None:
        self.base_url = base_url
        self.identity = identity
        self.pairing = None
        self.closed = False

    def pair(self, code: str, name: str) -> Pairing:
        assert code == "123456"
        assert name == "Workstation"
        self.pairing = Pairing("device-1", "token-1")
        return self.pairing

    def close(self) -> None:
        self.closed = True


def test_pairing_persists_only_non_sensitive_configuration(tmp_path: Path) -> None:
    credentials = MemoryCredentials()
    services = ConnectorServices.load(
        tmp_path, credential_store=credentials, client_factory=FakePairClient
    )

    services.pair("https://growth.example.com", "123456", "Workstation")

    assert services.runtime.client.pairing.device_id == "device-1"
    assert credentials.value.device_token == "token-1"
    config_text = (tmp_path / "connector.json").read_text(encoding="utf-8")
    assert "https://growth.example.com" in config_text
    assert "token-1" not in config_text
    assert services.config.device_name == "Workstation"


def test_existing_credentials_restore_paired_client(tmp_path: Path) -> None:
    credentials = MemoryCredentials()
    services = ConnectorServices.load(
        tmp_path, credential_store=credentials, client_factory=FakePairClient
    )
    services.pair("https://growth.example.com", "123456", "Workstation")

    restored = ConnectorServices.load(
        tmp_path, credential_store=credentials, client_factory=FakePairClient
    )

    assert restored.runtime.client.pairing == Pairing("device-1", "token-1")
