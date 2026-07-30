import hashlib
from pathlib import Path

LANGUAGES = {
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
}


def build_manifest(repository: Path, files: list[Path]) -> dict:
    root = Path(repository).resolve(strict=True)
    branch, commit = _read_head(root / ".git")
    languages: dict[str, int] = {}
    for path in files:
        language = LANGUAGES.get(path.suffix.casefold())
        if language:
            languages[language] = languages.get(language, 0) + path.stat().st_size
    external_key = hashlib.sha256(str(root).casefold().encode()).hexdigest()
    return {
        "external_key": external_key,
        "name": root.name,
        "default_branch": branch,
        "languages": languages,
        "last_commit": commit,
    }


def _read_head(git_dir: Path) -> tuple[str, str]:
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return "detached", head
    reference = head.removeprefix("ref: ").strip()
    branch = reference.rsplit("/", 1)[-1]
    reference_file = git_dir / reference
    if reference_file.exists():
        return branch, reference_file.read_text(encoding="utf-8").strip()
    packed = git_dir / "packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            if line and not line.startswith(("#", "^")):
                commit, name = line.split(" ", 1)
                if name == reference:
                    return branch, commit
    return branch, ""

