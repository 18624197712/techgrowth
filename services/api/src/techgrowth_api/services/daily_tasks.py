from ..config import Settings
from ..domain.curriculum import CurriculumNode
from ..integrations.provider_settings import resolve_provider_settings
from ..workflows import AgentWorkflowService, build_curriculum_fallback


class DailyTaskService:
    def __init__(self, settings: Settings, growth, radar, provider_settings) -> None:
        self.settings = settings
        self.growth = growth
        self.radar = radar
        self.provider_settings = provider_settings

    @staticmethod
    def fallback_for(node: CurriculumNode, source_ids: list[str]):
        return build_curriculum_fallback(node, source_ids)

    async def generate(self):
        existing = self.growth.today_task()
        if existing is not None:
            return existing
        node = self.growth.next_curriculum_node()
        radar_items = self.radar.list_items()[:5]
        sources = [
            {"id": item.id, "content": f"{item.title}\n{item.summary}"} for item in radar_items
        ]
        if not sources:
            sources = [{"id": "curriculum-v1", "content": node.objective}]
        settings = resolve_provider_settings(
            self.settings, self.provider_settings.provider_values()
        )
        draft = await AgentWorkflowService(settings).generate_daily_task(
            node=node,
            sources=sources,
            recent_topics=self.growth.recent_topics(),
        )
        return self.growth.save_draft(draft, node.title)

    async def generate_from_radar(self, radar_item_id: str):
        if self.growth.today_task() is not None:
            raise ValueError("今日任务已存在，请完成后再创建新的雷达任务")
        item = self.radar.get(radar_item_id)
        if item is None:
            raise LookupError("Radar item not found")
        node = self.growth.next_curriculum_node()
        settings = resolve_provider_settings(
            self.settings, self.provider_settings.provider_values()
        )
        draft = await AgentWorkflowService(settings).generate_daily_task(
            node=node,
            sources=[{"id": item.id, "content": f"{item.title}\n{item.summary}"}],
            recent_topics=self.growth.recent_topics(),
        )
        return self.growth.save_draft(draft, node.title)
