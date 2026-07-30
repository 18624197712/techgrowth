from datetime import UTC, datetime

import pytest

from techgrowth_api.integrations.radar_collector import RadarSourceResult
from techgrowth_api.integrations.radar_sources import IngestCandidate
from techgrowth_api.services import radar_jobs as radar_jobs_module


def candidate(source_key: str = "official:item-1") -> IngestCandidate:
    return IngestCandidate(
        source_key=source_key,
        title="Agent Runtime 2.0",
        summary="Durable agent execution with explicit state boundaries.",
        source_url="https://example.com/agent-runtime",
        source_name="Official AI",
        topic="Agent engineering",
        published_at=datetime.now(UTC),
        credibility=0.95,
    )


class FakeCollector:
    def __init__(self, results: list[RadarSourceResult]) -> None:
        self.results = results
        self.calls = 0

    async def collect(self) -> list[RadarSourceResult]:
        self.calls += 1
        return self.results


@pytest.mark.asyncio
async def test_radar_job_records_partial_source_failure(client) -> None:
    job = client.app.state.services.radar_jobs
    job.collector = FakeCollector(
        [
            RadarSourceResult("official", [candidate()], ""),
            RadarSourceResult("broken", [], "HTTP 503"),
        ]
    )

    result = await job.run()

    assert result["status"] == "partial"
    assert result["successful_sources"] == 1
    assert result["total_sources"] == 2
    assert result["failed_sources"] == ["broken"]
    assert result["inserted_items"] == 1
    assert "https://" not in str(result)
    assert client.app.state.services.radar_jobs.status()["status"] == "partial"


@pytest.mark.asyncio
async def test_automatic_radar_job_is_idempotent_for_the_day(client) -> None:
    collector = FakeCollector([RadarSourceResult("official", [candidate()], "")])
    job = client.app.state.services.radar_jobs
    job.collector = collector

    first = await job.run()
    second = await job.run()

    assert first["id"] == second["id"]
    assert collector.calls == 1


@pytest.mark.asyncio
async def test_radar_job_only_embeds_new_source_items(client, monkeypatch) -> None:
    existing = candidate("official:existing")
    new = candidate("official:new")
    client.app.state.services.radar.upsert([existing])
    embedded: list[str] = []

    class FakeEmbeddingModel:
        def __init__(self, settings) -> None:
            self.embedding_configured = True

        async def embedding(self, text: str) -> list[float]:
            embedded.append(text)
            return [0.1] * 1536

    monkeypatch.setattr(radar_jobs_module, "ModelClient", FakeEmbeddingModel)
    job = client.app.state.services.radar_jobs
    job.collector = FakeCollector([RadarSourceResult("official", [existing, new], "")])

    result = await job.run(force=True)

    assert result["inserted_items"] == 1
    assert len(embedded) == 1
    assert new.title in embedded[0]


def test_authenticated_manual_radar_refresh_returns_run_status(authenticated_client) -> None:
    client, csrf = authenticated_client
    client.app.state.services.radar_jobs.collector = FakeCollector(
        [RadarSourceResult("official", [candidate("official:manual")], "")]
    )

    response = client.post("/api/v1/radar/refresh", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    status = client.get("/api/v1/radar/status")
    assert status.status_code == 200
    assert status.json()["inserted_items"] == 1
