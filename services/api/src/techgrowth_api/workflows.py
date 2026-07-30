import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .config import Settings
from .domain.curriculum import CurriculumNode
from .domain.tasks import TaskDraft, TaskPolicy
from .integrations.model_client import ModelClient, ModelClientError


class TaskState(TypedDict, total=False):
    node: CurriculumNode
    sources: list[dict]
    source_context: str
    task: TaskDraft


def build_untrusted_context(items: list[dict]) -> str:
    rendered = json.dumps(items, ensure_ascii=False)[:24_000]
    return f"<untrusted_sources>{rendered}</untrusted_sources>"


def _score_anchors(subject: str) -> dict[str, str]:
    return {
        "0": f"没有可检查的{subject}",
        "1": f"{subject}无法稳定运行",
        "2": f"{subject}只覆盖主要成功路径",
        "3": f"{subject}满足任务要求并通过验收",
        "4": f"{subject}还覆盖失败路径并解释关键决策",
    }


def build_curriculum_fallback(node: CurriculumNode, source_ids: list[str]) -> TaskDraft:
    return TaskDraft(
        title=f"实作：{node.title}",
        topic=node.title,
        expected_minutes=35,
        objective=node.objective,
        curriculum_version="v1",
        track_key=node.track_key,
        stage_key=node.stage_key,
        node_key=node.key,
        prerequisites=list(node.prerequisites) or ["准备一个可以运行测试的练习仓库"],
        instructions=[
            {
                "action": f"阅读引用资料，写下完成“{node.objective}”所需的输入、输出和失败边界",
                "minutes": 8,
                "expected_result": "report.md 中列出至少一个成功条件和一个失败条件",
            },
            {
                "action": f"在独立分支实现围绕“{node.objective}”的最小可运行实验",
                "minutes": 17,
                "expected_result": "实现可以由单条命令运行，并产生可观察输出",
            },
            {
                "action": "补充成功与失败样例，运行测试并在 report.md 记录命令和结果",
                "minutes": 10,
                "expected_result": "测试通过，报告包含真实命令、结果和一个改进点",
            },
        ],
        source_ids=source_ids,
        submission_kinds=["commit", "report"],
        deliverables=["包含最小实验的 Git Commit", "记录验收结果的 report.md"],
        acceptance_checks=[
            {
                "method": "command",
                "instruction": "运行仓库现有测试命令",
                "expected_result": "进程退出码为 0，新增成功与失败样例均通过",
            },
            {
                "method": "inspection",
                "instruction": "检查 report.md 和本次 Commit diff",
                "expected_result": "报告中的命令可复现，diff 只包含本任务相关改动",
            },
        ],
        rubric=[
            {
                "key": "correctness",
                "label": "实现正确性",
                "description": "实现满足节点目标并产生可观察结果",
                "critical": True,
                "score_anchors": _score_anchors("实现"),
            },
            {
                "key": "testing",
                "label": "验证与证据",
                "description": "成功和失败路径均有可复现证据",
                "critical": False,
                "score_anchors": _score_anchors("验证证据"),
            },
        ],
        remediation_hint="只补做最低分 Rubric 项，并重新运行对应验收检查",
    )


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
        node = state["node"]
        source_ids = [str(item["id"]) for item in state["sources"]]
        if not self.model.configured:
            return {"task": build_curriculum_fallback(node, source_ids)}
        prompt = (
            f"Curriculum node: {node.key}\nStage: {node.stage_key}\n"
            f"Objective: {node.objective}\nPrerequisites: {list(node.prerequisites)}\n"
            f"Required deliverable kinds: {list(node.deliverable_kinds)}\n"
            f"Allowed source IDs: {source_ids}\nSources: {state['source_context']}"
        )
        try:
            task = await self.model.structured(
                "Design one concrete, evidence-backed 30-45 minute programming exercise. "
                "Use structured steps, observable expected results, two acceptance checks, "
                "and complete 0-4 rubric anchors. Return Chinese task content.",
                prompt,
                TaskDraft,
            )
            if not task.source_ids or not set(task.source_ids) <= set(source_ids):
                raise ValueError("model returned an unknown source ID")
            task = task.model_copy(
                update={
                    "curriculum_version": "v1",
                    "track_key": node.track_key,
                    "stage_key": node.stage_key,
                    "node_key": node.key,
                    "topic": node.title,
                }
            )
            TaskPolicy.validate(task, [])
            return {"task": task}
        except (ModelClientError, ValueError):
            return {"task": build_curriculum_fallback(node, source_ids)}

    async def generate_daily_task(
        self,
        node: CurriculumNode,
        sources: list[dict],
        recent_topics: list[tuple[str, object]],
    ) -> TaskDraft:
        result = await self.task_graph.ainvoke({"node": node, "sources": sources})
        return TaskPolicy.validate(result["task"], recent_topics)
