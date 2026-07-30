import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from ..config import Settings
from ..integrations.model_client import ModelClient, ModelClientError
from ..integrations.provider_settings import resolve_provider_settings
from ..integrations.radar_collector import RadarCollector
from ..models import AgentRunRecord


class RadarJobService:
    def __init__(self, session_factory, settings: Settings, radar, provider_settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.radar = radar
        self.provider_settings = provider_settings
        self.collector = RadarCollector()
        self.lock = asyncio.Lock()

    def _latest_success_today(self) -> AgentRunRecord | None:
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session_factory() as db:
            item = db.scalar(
                select(AgentRunRecord)
                .where(
                    AgentRunRecord.workflow == "radar_collect",
                    AgentRunRecord.status.in_(("succeeded", "partial")),
                    AgentRunRecord.created_at >= start,
                )
                .order_by(AgentRunRecord.created_at.desc())
                .limit(1)
            )
            if item:
                db.expunge(item)
            return item

    @staticmethod
    def _public(item: AgentRunRecord) -> dict:
        details = item.details or {}
        return {
            "id": item.id,
            "status": item.status,
            "successful_sources": details.get("successful_sources", 0),
            "failed_sources": details.get("failed_sources", []),
            "inserted_items": details.get("inserted_items", 0),
            "embedding_failures": details.get("embedding_failures", 0),
            "created_at": item.created_at,
        }

    def status(self) -> dict:
        with self.session_factory() as db:
            item = db.scalar(
                select(AgentRunRecord)
                .where(AgentRunRecord.workflow == "radar_collect")
                .order_by(AgentRunRecord.created_at.desc())
                .limit(1)
            )
            if not item:
                return {
                    "id": "",
                    "status": "never",
                    "successful_sources": 0,
                    "failed_sources": [],
                    "inserted_items": 0,
                    "embedding_failures": 0,
                    "created_at": None,
                }
            return self._public(item)

    async def run(self, force: bool = False) -> dict:
        async with self.lock:
            if not force and (existing := self._latest_success_today()) is not None:
                return self._public(existing)
            provider = resolve_provider_settings(
                self.settings, self.provider_settings.provider_values()
            )
            with self.session_factory() as db:
                run = AgentRunRecord(
                    workflow="radar_collect",
                    model=provider.embedding_model,
                    status="running",
                    details={},
                )
                db.add(run)
                db.commit()
                run_id = run.id

            results = await self.collector.collect()
            successful = [result for result in results if not result.error]
            failed = [result for result in results if result.error]
            candidates = [candidate for result in successful for candidate in result.candidates]
            embeddings: dict[str, list[float]] = {}
            embedding_failures = 0
            model = ModelClient(provider)
            if model.embedding_configured:
                for candidate in candidates:
                    try:
                        vector = await model.embedding(f"{candidate.title}\n{candidate.summary}")
                        if len(vector) != 1536:
                            raise ModelClientError("Embedding dimension must be 1536")
                        embeddings[candidate.source_key] = vector
                    except ModelClientError:
                        embedding_failures += 1

            inserted = self.radar.upsert(candidates, embeddings)
            references = self.radar.ids_for_source_keys(
                [candidate.source_key for candidate in candidates]
            )
            status = "failed" if not successful else "partial" if failed else "succeeded"
            details = {
                "successful_sources": len(successful),
                "failed_sources": [result.source_id for result in failed],
                "source_errors": {result.source_id: result.error for result in failed},
                "inserted_items": inserted,
                "embedding_failures": embedding_failures,
            }
            with self.session_factory() as db:
                run = db.get(AgentRunRecord, run_id)
                run.status = status
                run.details = details
                run.references = references
                run.error = f"{len(failed)} source(s) failed" if failed else ""
                db.commit()
                db.refresh(run)
                return self._public(run)
