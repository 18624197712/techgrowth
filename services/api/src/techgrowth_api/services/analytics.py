from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..models import (
    AgentRunRecord,
    LearningTaskRecord,
    RadarItemRecord,
    RepositoryRecord,
    ReviewRecord,
)

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": None}


class AnalyticsService:
    def __init__(self, session_factory, curriculum) -> None:
        self.session_factory = session_factory
        self.curriculum = curriculum

    def overview(self, range_key: str) -> dict:
        learning = self.learning(range_key)
        radar = self.radar(range_key)
        repositories = self.repositories(range_key)
        ai_runs = self.ai_runs(range_key)
        metrics = learning["metrics"][:3]
        metrics.extend(radar["metrics"][:1])
        metrics.extend(repositories["metrics"][:1])
        metrics.extend(ai_runs["metrics"][:1])
        return {
            "range": range_key,
            "metrics": metrics,
            "track_progress": learning["track_progress"],
        }

    def learning(self, range_key: str) -> dict:
        cutoff = self._cutoff(range_key)
        with self.session_factory() as db:
            tasks = list(db.scalars(select(LearningTaskRecord)).all())
            reviews = list(db.scalars(select(ReviewRecord)).all())
        tasks = [item for item in tasks if self._included(item.created_at, cutoff)]
        reviews = [item for item in reviews if self._included(item.created_at, cutoff)]
        passed_tasks = [item for item in tasks if item.status == "passed"]
        passed_reviews = [item for item in reviews if item.passed]
        pass_rate = round(len(passed_reviews) * 100 / len(reviews), 1) if reviews else 0
        return {
            "range": range_key,
            "metrics": [
                self._metric(
                    "learning_minutes",
                    "有效学习",
                    sum(item.expected_minutes for item in passed_tasks),
                    "分钟",
                    "时间范围内通过审阅任务的计划分钟数之和",
                    {"passed_tasks": len(passed_tasks)},
                ),
                self._metric(
                    "task_pass_rate",
                    "任务通过率",
                    pass_rate,
                    "%",
                    "通过审阅数除以全部已审阅任务数",
                    {"passed": len(passed_reviews), "reviewed": len(reviews)},
                ),
                self._metric(
                    "completed_nodes",
                    "完成课程节点",
                    sum(item.completed_nodes for item in self.curriculum.progress()),
                    "个",
                    "所有路线中已有通过证据的课程节点数",
                    {item.track_key: item.completed_nodes for item in self.curriculum.progress()},
                ),
            ],
            "track_progress": [
                {
                    "track_key": item.track_key,
                    "label": item.label,
                    "completed_nodes": item.completed_nodes,
                    "total_nodes": item.total_nodes,
                    "current_stage": item.current_stage,
                }
                for item in self.curriculum.progress()
            ],
        }

    def radar(self, range_key: str) -> dict:
        cutoff = self._cutoff(range_key)
        with self.session_factory() as db:
            items = list(db.scalars(select(RadarItemRecord)).all())
        items = [item for item in items if self._included(item.created_at, cutoff)]
        topics: dict[str, int] = {}
        for item in items:
            topics[item.topic] = topics.get(item.topic, 0) + 1
        average = round(sum(item.relevance for item in items) * 100 / len(items), 1) if items else 0
        return {
            "range": range_key,
            "metrics": [
                self._metric(
                    "radar_items",
                    "新增技术信号",
                    len(items),
                    "条",
                    "时间范围内成功保存并去重的雷达条目数",
                    {"topics": topics},
                ),
                self._metric(
                    "average_relevance",
                    "平均个人相关度",
                    average,
                    "%",
                    "雷达条目的个人相关度算术平均值",
                    {"items": len(items)},
                ),
            ],
            "topics": topics,
        }

    def repositories(self, range_key: str) -> dict:
        cutoff = self._cutoff(range_key)
        with self.session_factory() as db:
            items = list(db.scalars(select(RepositoryRecord)).all())
        synced = [
            item
            for item in items
            if item.last_synced_at and self._included(item.last_synced_at, cutoff)
        ]
        languages: dict[str, int] = {}
        for item in items:
            for language, count in item.languages.items():
                languages[language] = languages.get(language, 0) + int(count)
        return {
            "range": range_key,
            "metrics": [
                self._metric(
                    "connected_repositories",
                    "已连接仓库",
                    len(items),
                    "个",
                    "连接器或 GitHub 已登记的唯一仓库数",
                    {"synced_in_range": len(synced)},
                ),
                self._metric(
                    "repository_languages",
                    "识别语言",
                    len(languages),
                    "种",
                    "全部已连接仓库语言统计中的唯一语言数",
                    languages,
                ),
            ],
            "repositories": [
                {
                    "id": item.id,
                    "name": item.name,
                    "provider": item.provider,
                    "languages": item.languages,
                    "last_synced_at": item.last_synced_at,
                }
                for item in items
            ],
        }

    def ai_runs(self, range_key: str) -> dict:
        cutoff = self._cutoff(range_key)
        with self.session_factory() as db:
            items = list(db.scalars(select(AgentRunRecord)).all())
        items = [item for item in items if self._included(item.created_at, cutoff)]
        successful = sum(item.status in {"success", "completed"} for item in items)
        success_rate = round(successful * 100 / len(items), 1) if items else 0
        tokens = sum(item.input_tokens + item.output_tokens for item in items)
        return {
            "range": range_key,
            "metrics": [
                self._metric(
                    "ai_success_rate",
                    "AI 运行成功率",
                    success_rate,
                    "%",
                    "成功或完成的 AgentRun 数除以全部 AgentRun 数",
                    {"successful": successful, "total": len(items)},
                ),
                self._metric(
                    "ai_tokens",
                    "Token 用量",
                    tokens,
                    "token",
                    "AgentRun 记录的输入与输出 token 之和",
                    {"runs": len(items)},
                ),
            ],
        }

    @staticmethod
    def _metric(key, label, value, unit, definition, components) -> dict:
        return {
            "key": key,
            "label": label,
            "value": value,
            "unit": unit,
            "definition": definition,
            "components": components,
        }

    @staticmethod
    def _cutoff(range_key: str) -> datetime | None:
        if range_key not in RANGE_DAYS:
            raise ValueError("统计范围必须是 7d、30d、90d 或 all")
        days = RANGE_DAYS[range_key]
        return datetime.now(UTC) - timedelta(days=days) if days else None

    @staticmethod
    def _included(value: datetime, cutoff: datetime | None) -> bool:
        if cutoff is None:
            return True
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        return aware >= cutoff
