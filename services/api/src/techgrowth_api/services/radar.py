from dataclasses import asdict

from sqlalchemy import select

from ..integrations.radar_sources import IngestCandidate
from ..models import RadarItemRecord


class RadarService:
    SEED = {
        "source_key": "seed-agent-engineering",
        "title": "从可验证工作流开始构建 Agent",
        "summary": "将规划、执行和评估拆成有边界的状态节点，并记录引用与运行结果。",
        "source_url": "https://langchain-ai.github.io/langgraph/",
        "source_name": "LangGraph Documentation",
        "topic": "Agent engineering",
        "credibility": 0.95,
        "relevance": 0.92,
        "relevance_reason": "与你当前的 AI Agent 实战方向直接相关。",
    }

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def list_items(self) -> list[RadarItemRecord]:
        with self.session_factory() as db:
            items = db.scalars(
                select(RadarItemRecord).order_by(RadarItemRecord.relevance.desc())
            ).all()
            if not items:
                item = RadarItemRecord(**self.SEED)
                db.add(item)
                db.commit()
                items = [item]
            return items

    def upsert(self, candidates: list[IngestCandidate]) -> int:
        inserted = 0
        with self.session_factory() as db:
            for candidate in candidates:
                existing = db.scalar(
                    select(RadarItemRecord).where(
                        RadarItemRecord.source_key == candidate.source_key
                    )
                )
                if existing:
                    continue
                db.add(RadarItemRecord(**asdict(candidate)))
                inserted += 1
            db.commit()
        return inserted
