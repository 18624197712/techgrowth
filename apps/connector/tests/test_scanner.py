from pathlib import Path

import pytest

from techgrowth_connector.scanner import RepositoryScanner, UnsafePathError


def make_repository(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    return path


def test_rejects_files_outside_authorized_roots(tmp_path: Path) -> None:
    root = tmp_path / "authorized"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("print('no')", encoding="utf-8")
    scanner = RepositoryScanner([root])

    with pytest.raises(UnsafePathError, match="authorized"):
        scanner.require_authorized(outside)


def test_rejects_symlink_that_escapes_authorized_root(tmp_path: Path) -> None:
    root = tmp_path / "authorized"
    root.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("secret = True", encoding="utf-8")
    link = root / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable on this Windows host")

    with pytest.raises(UnsafePathError, match="symbolic link"):
        RepositoryScanner([root]).require_authorized(link)


def test_file_listing_honors_gitignore_and_sensitive_file_rules(tmp_path: Path) -> None:
    repo = make_repository(tmp_path / "repo")
    (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (repo / "main.py").write_text("print('ok')", encoding="utf-8")
    (repo / "ignored.py").write_text("print('ignored')", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (repo / "private.pem").write_text("PRIVATE KEY", encoding="utf-8")
    (repo / "binary.bin").write_bytes(b"\x00\x01\x02")
    dependencies = repo / "node_modules"
    dependencies.mkdir()
    (dependencies / "package.js").write_text("ignored", encoding="utf-8")

    files = RepositoryScanner([tmp_path]).list_shareable_files(repo)

    assert [item.relative_to(repo).as_posix() for item in files] == ["main.py"]


def test_file_listing_rejects_oversized_files(tmp_path: Path) -> None:
    repo = make_repository(tmp_path / "repo")
    (repo / "small.py").write_text("ok", encoding="utf-8")
    (repo / "large.py").write_bytes(b"x" * 33)

    files = RepositoryScanner([tmp_path], max_file_bytes=32).list_shareable_files(repo)

    assert [item.name for item in files] == ["small.py"]


def test_repository_discovery_skips_dependency_directories(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    expected = make_repository(root / "product")
    make_repository(root / "node_modules" / "dependency")

    repositories = RepositoryScanner([root]).discover_repositories()

    assert repositories == [expected.resolve()]
