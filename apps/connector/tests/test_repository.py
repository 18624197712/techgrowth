from pathlib import Path

from techgrowth_connector.repository import build_manifest


def test_manifest_reads_git_head_and_language_counts_without_executing_code(tmp_path: Path) -> None:
    repo = tmp_path / "product"
    git = repo / ".git"
    refs = git / "refs" / "heads"
    refs.mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (refs / "main").write_text("abc123\n", encoding="utf-8")
    (repo / "main.py").write_text("print('ok')", encoding="utf-8")
    (repo / "web.ts").write_text("export {}", encoding="utf-8")

    manifest = build_manifest(repo, [repo / "main.py", repo / "web.ts"])

    assert manifest["name"] == "product"
    assert manifest["default_branch"] == "main"
    assert manifest["last_commit"] == "abc123"
    assert manifest["languages"] == {"Python": 11, "TypeScript": 9}
    assert len(manifest["external_key"]) == 64
