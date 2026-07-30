import pytest

from techgrowth_api.domain.repositories import canonical_remote_url
from techgrowth_api.schemas import RepositoryManifestRequest


@pytest.mark.parametrize(
    "remote",
    [
        "git@github.com:Owner/Repo.git",
        "ssh://git@github.com/Owner/Repo.git",
        "https://github.com/Owner/Repo/",
    ],
)
def test_canonical_remote_normalizes_github_ssh_and_https(remote: str) -> None:
    assert canonical_remote_url(remote) == "github.com/owner/repo"


def test_connector_observation_uses_canonical_remote_identity(client) -> None:
    repositories = client.app.state.services.repositories

    first = repositories.register_connector(
        "device-1",
        RepositoryManifestRequest(
            external_key="local-a",
            local_fingerprint="root/product",
            remote_url="git@github.com:Owner/Repo.git",
            name="Repo",
        ),
    )
    second = repositories.register_connector(
        "device-1",
        RepositoryManifestRequest(
            external_key="local-a",
            local_fingerprint="root/product",
            remote_url="https://github.com/owner/repo/",
            name="Repo",
        ),
    )

    assert first.id == second.id
    assert second.canonical_remote == "github.com/owner/repo"
    assert second.match_status == "matched"


def test_local_repository_without_remote_remains_explicitly_unmatched(client) -> None:
    repository = client.app.state.services.repositories.register_connector(
        "device-1",
        RepositoryManifestRequest(
            external_key="local-only",
            local_fingerprint="root/local-only",
            name="local-only",
        ),
    )

    assert repository.match_status == "unmatched"
