import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .config import Settings
from .domain.curriculum import CURRICULUM, CurriculumNode
from .domain.tasks import TaskDraft, TaskPolicy
from .integrations.model_client import ModelClient, ModelClientError


class TaskState(TypedDict, total=False):
    node: CurriculumNode
    sources: list[dict]
    source_context: str
    task: TaskDraft
    variation: str


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


def build_curriculum_fallback(
    node: CurriculumNode, source_ids: list[str], variation: str = ""
) -> TaskDraft:
    task_kind = "algorithm" if node.track_key == "algorithms" else "coding"
    return TaskDraft(
        title=f"{'专项练习' if variation else '实作'}：{node.title}",
        topic=node.title,
        expected_minutes=35,
        objective=node.objective,
        curriculum_version=(
            CURRICULUM.version
            if any(track.key == node.track_key for track in CURRICULUM.tracks)
            else "v1"
        ),
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
        task_kind=task_kind,
        learning_objectives=[
            f"解释“{node.objective}”涉及的核心概念与适用边界",
            f"实现并验证一个能够证明“{node.objective}”的最小实验",
        ],
        theory_brief=(
            f"本题聚焦“{node.objective}”。开始编码前，需要先写清关键概念、输入输出、"
            "成功条件和失败边界，并说明所选方案为何适合当前约束。"
        ),
        problem_statement=(
            f"在一个独立练习分支中完成“{node.objective}”的最小可运行实现。"
            "实现必须包含一个正常场景和一个失败场景，使用可重复命令验证结果，"
            "并在 report.md 中记录设计取舍、真实输出和仍可改进之处。"
        ),
        constraints=[
            "总投入控制在 30 至 45 分钟，不引入与目标无关的框架或重构",
            "不得只提交文字结论；实现或答案必须有可复现的验收证据",
            "失败场景必须被测试或检查明确覆盖",
        ],
        starter_context="使用当前授权仓库的独立分支；若没有合适仓库，创建最小练习目录。",
        hints=[
            "先把成功条件和失败边界写成两个可检查的例子，再选择最小实现。",
            "让核心逻辑与外部 I/O 分离，使正常和失败场景都能通过单条命令验证。",
            "先完成最短成功路径，再加入失败用例；用 report.md 对照每条验收标准记录结果。",
        ],
        solution_outline=(
            "参考思路：先定义输入、输出和不变量，把核心行为实现为可独立测试的最小单元；"
            "随后分别构造成功与失败样例，执行测试命令并把输出、取舍和改进点记录到报告。"
        ),
        generation_source="rules",
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
            return {
                "task": build_curriculum_fallback(
                    node, source_ids, state.get("variation", "")
                )
            }
        prompt = (
            f"Curriculum node: {node.key}\nStage: {node.stage_key}\n"
            f"Objective: {node.objective}\nPrerequisites: {list(node.prerequisites)}\n"
            f"Required deliverable kinds: {list(node.deliverable_kinds)}\n"
            f"Variation requirement: {state.get('variation') or 'initial exercise'}\n"
            f"Allowed source IDs: {source_ids}\nSources: {state['source_context']}"
        )
        try:
            task = await self.model.structured(
                "Design one concrete, evidence-backed 30-45 minute programming exercise. "
                "Include theory, an explicit problem statement, constraints, three progressive "
                "hints, a solution outline, structured steps, observable expected results, two "
                "acceptance checks, and complete 0-4 rubric anchors. The three hints must progress "
                "from concept, to decomposition, to pseudocode or key APIs. The solution outline "
                "must explain reasoning and pseudocode without providing a complete "
                "implementation. "
                "Return Chinese task content grounded in the curriculum node and allowed sources.",
                prompt,
                TaskDraft,
            )
            if not task.source_ids or not set(task.source_ids) <= set(source_ids):
                raise ValueError("model returned an unknown source ID")
            task = task.model_copy(
                update={
                    "curriculum_version": (
                        CURRICULUM.version
                        if any(track.key == node.track_key for track in CURRICULUM.tracks)
                        else "v1"
                    ),
                    "track_key": node.track_key,
                    "stage_key": node.stage_key,
                    "node_key": node.key,
                    "topic": node.title,
                    "generation_source": "ai",
                }
            )
            TaskPolicy.validate(task, [])
            return {"task": task}
        except (ModelClientError, ValueError):
            return {
                "task": build_curriculum_fallback(
                    node, source_ids, state.get("variation", "")
                )
            }

    async def generate_daily_task(
        self,
        node: CurriculumNode,
        sources: list[dict],
        recent_topics: list[tuple[str, object]],
        variation: str = "",
    ) -> TaskDraft:
        result = await self.task_graph.ainvoke(
            {"node": node, "sources": sources, "variation": variation}
        )
        return TaskPolicy.validate(result["task"], recent_topics)
