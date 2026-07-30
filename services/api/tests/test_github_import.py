from datetime import UTC, datetime

from techgrowth_api.integrations.github import GitHubRepository
from techgrowth_api.schemas import RepositoryManifestRequest


class FakeGitHubClient:
    def __init__(self, token: str) -> None:
        assert token == "github-secret-token"

    async def repositories(self) -> list[GitHubRepository]:
        return [
            GitHubRepository(
                id=7,
                name="repo",
                full_name="Owner/Repo",
                private=True,
                default_branch="main",
                pushed_at=datetime(2026, 7, 30, tzinfo=UTC),
                languages={"Python": 100},
                html_url="https://github.com/Owner/Repo",
            )
        ]


def test_github_pat_is_validated_encrypted_and_never_returned(
    authenticated_client, monkeypatch
) -> None:
    client, csrf = authenticated_client
    monkeypatch.setattr("techgrowth_api.routers.connector.GitHubClient", FakeGitHubClient)

    response = client.put(
        "/api/v1/setup/github",
        headers={"X-CSRF-Token": csrf},
        json={"token": "github-secret-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert "github-secret-token" not in response.text
    assert client.get("/api/v1/setup").json()["github"] == {"configured": True}
    assert "github-secret-token" not in str(
        client.app.state.services.settings.encrypted_value("github.token")
    )


def test_github_import_merges_matching_connector_repository(
    authenticated_client, monkeypatch
) -> None:
    client, csrf = authenticated_client
    services = client.app.state.services
    services.repositories.register_connector(
        "device-1",
        RepositoryManifestRequest(
            external_key="local-repo",
            local_fingerprint="projects/repo",
            remote_url="git@github.com:Owner/Repo.git",
            name="repo",
        ),
    )
    services.settings.save_secret("github.token", "github-secret-token")
    monkeypatch.setattr("techgrowth_api.routers.connector.GitHubClient", FakeGitHubClient)

    response = client.post("/api/v1/repositories/github/import", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    repositories = client.get("/api/v1/repositories").json()
    assert len(repositories) == 1
    assert repositories[0]["provider"] == "connector+github"
    assert repositories[0]["canonical_remote"] == "github.com/owner/repo"
    assert repositories[0]["match_status"] == "matched"
