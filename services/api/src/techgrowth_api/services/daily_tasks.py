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
        node = self.growth.next_curriculum_node()
        if existing is not None and existing.node_key == node.key:
            return existing
        sources = self._sources_for(node)
        settings = resolve_provider_settings(
            self.settings, self.provider_settings.provider_values()
        )
        draft = await AgentWorkflowService(settings).generate_daily_task(
            node=node,
            sources=sources,
            recent_topics=self.growth.recent_topics(),
        )
        if existing is None:
            return self.growth.save_draft(draft, node.title)
        draft = draft.model_copy(
            update={
                "replaces_task_id": existing.id,
                "regeneration_reason": "课程路线或等级已变更，自动对齐当前节点",
            }
        )
        if existing.status in {"ready", "open"}:
            return self.growth.replace_task(
                existing.id,
                draft,
                node.title,
                f"curriculum-sync:{existing.id}:{node.key}",
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
        node = self.growth.next_curriculum_node()
        settings = resolve_provider_settings(
            self.settings, self.provider_settings.provider_values()
        )
        sources = self._sources_for(node)
        draft = await AgentWorkflowService(settings).generate_daily_task(
            node=node,
            sources=sources,
            recent_topics=[
                item
                for item in self.growth.recent_topics()
                if item[0].casefold() != task.topic.casefold()
            ],
            variation=(
                f"重新出题原因：{reason}。必须保持课程节点和难度不变，但题目场景、"
                f"问题描述和验收样例必须明显区别于上一题“{task.title}”。"
            ),
        )
        draft = draft.model_copy(
            update={"replaces_task_id": task.id, "regeneration_reason": reason}
        )
        return self.growth.replace_task(task.id, draft, node.title, idempotency_key)

    def _sources_for(self, node: CurriculumNode) -> list[dict]:
        keywords = {item.casefold() for item in node.radar_keywords}
        radar_items = [
            item
            for item in self.radar.list_items()
            if any(
                keyword in f"{item.title} {item.summary} {item.topic}".casefold()
                for keyword in keywords
            )
        ][:5]
        sources = [
            {"id": item.id, "content": f"{item.title}\n{item.summary}"} for item in radar_items
        ]
        return sources or [{"id": "curriculum-v2", "content": node.objective}]
