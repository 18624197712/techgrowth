from ..config import Settings
from ..domain.curriculum import CURRICULUM, LEGACY_CURRICULUM, CurriculumNode
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

    async def regenerate(self, task_id: str, reason: str, idempotency_key: str):
        existing = self.growth.find_regeneration(idempotency_key)
        if existing is not None:
            return existing
        task = self.growth.get_task(task_id)
        if task is None:
            raise LookupError("Task not found")
        if task.status not in {"ready", "open"}:
            raise ValueError("已提交或已完成的任务不能重新出题")
        catalog = CURRICULUM if task.curriculum_version == "v2" else LEGACY_CURRICULUM
        try:
            node = catalog.node(task.node_key)
        except StopIteration as exc:
            raise ValueError("旧任务没有可用于重新出题的课程节点") from exc
        settings = resolve_provider_settings(
            self.settings, self.provider_settings.provider_values()
        )
        sources = [
            {"id": source_id, "content": task.objective} for source_id in task.source_ids
        ] or [{"id": f"curriculum-{catalog.version}", "content": task.objective}]
        draft = await AgentWorkflowService(settings).generate_daily_task(
            node=node,
            sources=sources,
            recent_topics=[
                item
                for item in self.growth.recent_topics()
                if item[0].casefold() != task.topic.casefold()
            ],
        )
        draft = draft.model_copy(
            update={"replaces_task_id": task.id, "regeneration_reason": reason}
        )
        return self.growth.replace_task(task.id, draft, node.title, idempotency_key)
