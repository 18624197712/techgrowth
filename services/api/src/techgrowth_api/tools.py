from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UnknownToolError(ValueError):
    pass


class EmptyArguments(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RegenerateTaskArguments(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reason: str = Field(default="由 AI 导师重新出题", min_length=2, max_length=500)


class SwitchTrackArguments(BaseModel):
    model_config = ConfigDict(extra="ignore")
    track_key: Literal["java", "python_ai", "go", "node_ts"]


class AlgorithmFrequencyArguments(BaseModel):
    model_config = ConfigDict(extra="ignore")
    days_per_week: int = Field(ge=0, le=7)


class RadarTaskArguments(BaseModel):
    model_config = ConfigDict(extra="ignore")
    radar_item_id: str = Field(min_length=1, max_length=64)


class RepositorySyncArguments(BaseModel):
    model_config = ConfigDict(extra="ignore")
    repository_id: str = Field(min_length=1, max_length=64)


@dataclass(frozen=True, slots=True)
class ToolContext:
    session_id: str
    page_context: dict


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    kind: Literal["result", "proposal"]
    name: str
    result: Any = None
    action: dict | None = None


ToolHandler = Callable[[BaseModel, ToolContext], Any | Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    arguments_model: type[BaseModel]
    write: bool
    handler: ToolHandler


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def openai_definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.arguments_model.model_json_schema(),
                },
            }
            for spec in self._specs.values()
        ]

    async def invoke(self, name: str, arguments: dict, context: ToolContext) -> ToolInvocation:
        spec = self._specs.get(name)
        if spec is None:
            raise UnknownToolError(f"Unknown tutor tool: {name}")
        validated = spec.arguments_model.model_validate(arguments)
        clean_arguments = validated.model_dump(mode="json")
        if spec.write:
            return ToolInvocation(
                kind="proposal",
                name=name,
                action={"action_type": name, "arguments": clean_arguments},
            )
        result = spec.handler(validated, context)
        if inspect.isawaitable(result):
            result = await result
        return ToolInvocation(kind="result", name=name, result=result)

    @classmethod
    def from_services(cls, services) -> ToolRegistry:
        def active_curriculum(_args, _context):
            return services.curriculum.payload()

        def skill_gaps(_args, _context):
            return {"skills": services.growth.profile()[:20]}

        def today_task(_args, _context):
            task = services.growth.today_task()
            if task is None:
                return {"task": None}
            return {
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "objective": task.objective,
                    "track_key": task.track_key,
                    "stage_key": task.stage_key,
                    "status": task.status,
                }
            }

        def radar_digest(_args, _context):
            return {
                "items": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "topic": item.topic,
                        "relevance": item.relevance,
                    }
                    for item in services.radar.list_items()[:8]
                ]
            }

        def repository_metrics(_args, _context):
            return {
                "repositories": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "languages": item.languages,
                        "last_commit": item.last_commit,
                    }
                    for item in services.connector.list_repositories()[:20]
                ]
            }

        def evidence(_args, _context):
            return {"skills": services.growth.profile()[:20]}

        def write_handler(_args, _context):
            return None
        return cls(
            [
                ToolSpec(
                    "get_active_curriculum",
                    "查询当前主路线、算法频率和各路线进度",
                    EmptyArguments,
                    False,
                    active_curriculum,
                ),
                ToolSpec(
                    "get_skill_gaps",
                    "查询由成长证据支持的技能短板",
                    EmptyArguments,
                    False,
                    skill_gaps,
                ),
                ToolSpec(
                    "get_today_task",
                    "查询今日任务的目标、阶段和状态",
                    EmptyArguments,
                    False,
                    today_task,
                ),
                ToolSpec(
                    "get_radar_digest",
                    "查询近期高相关性技术雷达摘要",
                    EmptyArguments,
                    False,
                    radar_digest,
                ),
                ToolSpec(
                    "get_repository_metrics",
                    "查询已连接仓库的技术栈和同步状态",
                    EmptyArguments,
                    False,
                    repository_metrics,
                ),
                ToolSpec(
                    "get_growth_evidence",
                    "查询近期成长证据和技能等级",
                    EmptyArguments,
                    False,
                    evidence,
                ),
                ToolSpec(
                    "regenerate_today_task",
                    "按当前课程节点重新生成今日任务",
                    RegenerateTaskArguments,
                    True,
                    write_handler,
                ),
                ToolSpec(
                    "switch_primary_track",
                    "切换当前主技术栈路线并保留其他路线进度",
                    SwitchTrackArguments,
                    True,
                    write_handler,
                ),
                ToolSpec(
                    "set_algorithm_frequency",
                    "设置每周由算法任务替代主路线任务的天数",
                    AlgorithmFrequencyArguments,
                    True,
                    write_handler,
                ),
                ToolSpec(
                    "create_task_from_radar",
                    "把指定雷达条目转换为课程兼容任务",
                    RadarTaskArguments,
                    True,
                    write_handler,
                ),
                ToolSpec(
                    "request_repository_sync",
                    "请求已连接设备同步指定仓库",
                    RepositorySyncArguments,
                    True,
                    write_handler,
                ),
            ]
        )
