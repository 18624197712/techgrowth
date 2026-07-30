from datetime import UTC, datetime

from sqlalchemy import or_, select

from ..domain.repositories import canonical_remote_url
from ..integrations.github import GitHubRepository
from ..models import RepositoryRecord
from ..schemas import RepositoryManifestRequest


class RepositoryService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def register_connector(
        self, device_id: str, manifest: RepositoryManifestRequest
    ) -> RepositoryRecord:
        canonical = canonical_remote_url(manifest.remote_url)
        now = datetime.now(UTC)
        with self.session_factory() as db:
            repository = db.scalar(
                select(RepositoryRecord).where(
                    or_(
                        RepositoryRecord.external_key == manifest.external_key,
                        RepositoryRecord.canonical_remote == canonical if canonical else False,
                    )
                )
            )
            if repository and repository.device_id not in (None, device_id):
                raise ValueError("Repository belongs to another connector")
            values = manifest.model_dump(exclude={"remote_url"})
            if repository is None:
                repository = RepositoryRecord(
                    device_id=device_id,
                    provider="connector",
                    canonical_remote=canonical or None,
                    match_status="matched" if canonical else "unmatched",
                    **values,
                )
                db.add(repository)
            else:
                repository.device_id = device_id
                repository.name = manifest.name
                repository.default_branch = manifest.default_branch
                repository.languages = manifest.languages
                repository.last_commit = manifest.last_commit
                repository.local_fingerprint = manifest.local_fingerprint
                if canonical:
                    repository.canonical_remote = canonical
                    repository.match_status = "matched"
                if repository.provider_id:
                    repository.provider = "connector+github"
            repository.last_synced_at = now
            db.commit()
            db.refresh(repository)
            db.expunge(repository)
            return repository

    def import_github(self, items: list[GitHubRepository]) -> list[RepositoryRecord]:
        imported: list[RepositoryRecord] = []
        with self.session_factory() as db:
            for item in items:
                provider_id = f"github:{item.id}"
                canonical = canonical_remote_url(
                    item.html_url or f"https://github.com/{item.full_name}"
                )
                repository = db.scalar(
                    select(RepositoryRecord).where(
                        or_(
                            RepositoryRecord.provider_id == provider_id,
                            RepositoryRecord.canonical_remote == canonical,
                        )
                    )
                )
                if repository is None:
                    repository = RepositoryRecord(
                        provider="github",
                        provider_id=provider_id,
                        external_key=provider_id,
                        canonical_remote=canonical,
                        match_status="matched",
                        name=item.name,
                    )
                    db.add(repository)
                repository.provider_id = provider_id
                repository.provider = "connector+github" if repository.device_id else "github"
                repository.canonical_remote = canonical
                repository.match_status = "matched"
                repository.name = item.name
                repository.default_branch = item.default_branch
                repository.languages = item.languages
                repository.last_synced_at = item.pushed_at
                imported.append(repository)
            db.commit()
            for repository in imported:
                db.refresh(repository)
                db.expunge(repository)
        return imported

    def list(self) -> list[RepositoryRecord]:
        with self.session_factory() as db:
            items = list(
                db.scalars(
                    select(RepositoryRecord).order_by(
                        RepositoryRecord.last_synced_at.desc().nullslast(),
                        RepositoryRecord.created_at.desc(),
                    )
                ).all()
            )
            for item in items:
                db.expunge(item)
            return items
