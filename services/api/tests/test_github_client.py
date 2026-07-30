import httpx
import pytest

from techgrowth_api.integrations.github import GitHubClient


@pytest.mark.asyncio
async def test_github_client_lists_private_repositories_and_languages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/repos":
            assert request.headers["authorization"] == "Bearer github-token"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 7,
                        "name": "agent-lab",
                        "full_name": "dev/agent-lab",
                        "private": True,
                        "default_branch": "main",
                        "pushed_at": "2026-07-29T10:00:00Z",
                    }
                ],
            )
        if request.url.path == "/repos/dev/agent-lab/languages":
            return httpx.Response(200, json={"Python": 920, "Shell": 80})
        return httpx.Response(404)

    client = GitHubClient("github-token", transport=httpx.MockTransport(handler))
    repositories = await client.repositories()

    assert repositories[0].private is True
    assert repositories[0].languages == {"Python": 92, "Shell": 8}
