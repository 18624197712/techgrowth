import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ConnectorConfig:
    path: Path
    server_url: str = ""
    device_name: str = "Windows Workstation"
    authorized_roots: list[str] = field(default_factory=list)
    repositories: dict[str, str] = field(default_factory=dict)
    update_feed_url: str = ""

    @classmethod
    def load(cls, path: Path) -> "ConnectorConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls(path=config_path)
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        allowed = {
            "server_url",
            "device_name",
            "authorized_roots",
            "repositories",
            "update_feed_url",
        }
        values = {key: value for key, value in payload.items() if key in allowed}
        return cls(path=config_path, **values)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload.pop("path")
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(self.path)

    def add_authorized_root(self, path: Path) -> None:
        resolved = str(Path(path).resolve(strict=True))
        if resolved not in self.authorized_roots:
            self.authorized_roots.append(resolved)
            self.save()

    def remove_authorized_root(self, path: str) -> None:
        self.authorized_roots = [item for item in self.authorized_roots if item != path]
        self.repositories = {
            key: value
            for key, value in self.repositories.items()
            if not Path(value).is_relative_to(Path(path))
        }
        self.save()
