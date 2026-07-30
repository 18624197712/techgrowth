import os
from pathlib import Path

from pathspec import PathSpec


class UnsafePathError(ValueError):
    pass


EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
}

SENSITIVE_NAMES = {
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
}

SENSITIVE_SUFFIXES = {".jks", ".key", ".keystore", ".p12", ".pem", ".pfx"}
BINARY_SUFFIXES = {
    ".7z",
    ".a",
    ".avi",
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lib",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".obj",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".tar",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}


class RepositoryScanner:
    def __init__(self, authorized_roots: list[Path], max_file_bytes: int = 1024 * 1024) -> None:
        if not authorized_roots:
            raise ValueError("at least one authorized root is required")
        self.authorized_roots = tuple(Path(root).resolve(strict=True) for root in authorized_roots)
        self.max_file_bytes = max_file_bytes

    def require_authorized(self, value: Path) -> Path:
        candidate = Path(value).absolute()
        for root in self.authorized_roots:
            try:
                relative = candidate.relative_to(root)
            except ValueError:
                continue
            current = root
            for part in relative.parts:
                current /= part
                if current.is_symlink():
                    raise UnsafePathError("symbolic link paths are not allowed")
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                raise UnsafePathError("path does not exist") from exc
            if resolved.is_relative_to(root):
                return resolved
        raise UnsafePathError("path is outside the authorized roots")

    def discover_repositories(self) -> list[Path]:
        repositories: set[Path] = set()
        for root in self.authorized_roots:
            for current, directories, _ in os.walk(root, followlinks=False):
                current_path = Path(current)
                directories[:] = [
                    name
                    for name in directories
                    if name not in EXCLUDED_DIRECTORIES and not (current_path / name).is_symlink()
                ]
                if (current_path / ".git").is_dir():
                    repositories.add(current_path.resolve())
                    directories.clear()
        return sorted(repositories, key=lambda item: str(item).casefold())

    def list_shareable_files(self, repository: Path) -> list[Path]:
        root = self.require_authorized(repository)
        if not (root / ".git").exists():
            raise UnsafePathError("path is not a Git repository")
        ignore_file = root / ".gitignore"
        ignore_spec = PathSpec.from_lines(
            "gitwildmatch",
            ignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if ignore_file.exists()
            else [],
        )
        accepted: list[Path] = []
        for current, directories, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name
                for name in directories
                if name not in EXCLUDED_DIRECTORIES
                and not (current_path / name).is_symlink()
                and not ignore_spec.match_file(
                    (current_path / name).relative_to(root).as_posix() + "/"
                )
            ]
            for name in filenames:
                candidate = current_path / name
                relative = candidate.relative_to(root).as_posix()
                if self._shareable(candidate, relative, ignore_spec):
                    accepted.append(candidate.resolve())
        return sorted(accepted, key=lambda item: item.relative_to(root).as_posix())

    def _shareable(self, path: Path, relative: str, ignore_spec: PathSpec) -> bool:
        lower_name = path.name.casefold()
        if path.is_symlink() or ignore_spec.match_file(relative):
            return False
        if lower_name == ".gitignore" or lower_name == ".env" or lower_name.startswith(".env."):
            return False
        if lower_name in SENSITIVE_NAMES or path.suffix.casefold() in SENSITIVE_SUFFIXES:
            return False
        if path.suffix.casefold() in BINARY_SUFFIXES:
            return False
        try:
            if path.stat().st_size > self.max_file_bytes:
                return False
            sample = path.read_bytes()[:8192]
        except OSError:
            return False
        return b"\x00" not in sample
