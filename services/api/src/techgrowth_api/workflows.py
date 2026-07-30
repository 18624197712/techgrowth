import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .config import Settings
from .domain.tasks import TaskDraft, TaskPolicy
from .integrations.model_client import ModelClient


class TaskState(TypedDict, total=False):
    skill: str
    topic: str
    sources: list[dict]
    source_context: str
    task: TaskDraft


def build_untrusted_context(items: list[dict]) -> str:
    rendered = json.dumps(items, ensure_ascii=False)[:24_000]
    return f"<untrusted_sources>{rendered}</untrusted_sources>"


class AgentWorkflowService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = ModelClient(settings)
        graph = StateGraph(TaskState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("draft_task", self._draft_task)
        graph.add_edge(START, "prepare_context")
        graph.add_edge("prepare_context", "draft_task")
        graph.add_edge("draft_task", END)
        self.task_graph = graph.compile()

    async def _prepare_context(self, state: TaskState) -> dict:
        return {"source_context": build_untrusted_context(state["sources"])}

    async def _draft_task(self, state: TaskState) -> dict:
        source_ids = [str(item["id"]) for item in state["sources"]]
        if self.model.configured:
            task = await self.model.structured(
                "You design one evidence-backed 30-45 minute programming exercise.",
                (
                    f"Skill: {state['skill']}\nTopic: {state['topic']}\n"
                    f"Sources: {state['source_context']}"
                ),
                TaskDraft,
            )
        else:
            task = TaskDraft(
                title=f"完成一个 {state['topic']} 的可验证实验",
                topic=state["topic"],
                expected_minutes=35,
                objective=f"通过 Python 实验练习 {state['skill']}。",
                instructions=["定义成功标准", "实现最小实验", "提交验证结果"],
                source_ids=source_ids,
                submission_kinds=["commit", "report", "answer"],
                rubric=[
                    {"key": "correctness", "label": "实现正确性", "critical": True},
                    {"key": "testing", "label": "验证与测试", "critical": False},
                ],
            )
        return {"task": task}

    async def generate_daily_task(
        self,
        skill: str,
        topic: str,
        sources: list[dict],
        recent_topics: list[tuple[str, object]],
    ) -> TaskDraft:
        result = await self.task_graph.ainvoke({"skill": skill, "topic": topic, "sources": sources})
        return TaskPolicy.validate(result["task"], recent_topics)
