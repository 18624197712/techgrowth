from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass(frozen=True, slots=True)
class GitHubRepository:
    id: int
    name: str
    full_name: str
    private: bool
    default_branch: str
    pushed_at: datetime
    languages: dict[str, int]


class GitHubClient:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.token = token
        self.transport = transport

    async def repositories(self) -> list[GitHubRepository]:
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
            transport=self.transport,
        ) as client:
            response = await client.get(
                "/user/repos", params={"visibility": "all", "affiliation": "owner", "per_page": 100}
            )
            response.raise_for_status()
            result: list[GitHubRepository] = []
            for item in response.json():
                language_response = await client.get(f"/repos/{item['full_name']}/languages")
                language_response.raise_for_status()
                raw_languages = language_response.json()
                total = sum(raw_languages.values()) or 1
                percentages = {
                    name: round(value * 100 / total) for name, value in raw_languages.items()
                }
                result.append(
                    GitHubRepository(
                        id=item["id"],
                        name=item["name"],
                        full_name=item["full_name"],
                        private=item["private"],
                        default_branch=item["default_branch"],
                        pushed_at=datetime.fromisoformat(item["pushed_at"].replace("Z", "+00:00")),
                        languages=percentages,
                    )
                )
            return result
