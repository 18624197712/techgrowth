from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field


class TaskStep(BaseModel):
    action: str = Field(min_length=5, max_length=500)
    minutes: int = Field(ge=3, le=30)
    expected_result: str = Field(min_length=3, max_length=500)


class AcceptanceCheck(BaseModel):
    method: Literal["command", "inspection", "answer"]
    instruction: str = Field(min_length=2, max_length=500)
    expected_result: str = Field(min_length=2, max_length=500)


class RubricCriterionDraft(BaseModel):
    key: str
    label: str
    description: str = ""
    critical: bool = False
    score_anchors: dict[str, str] = Field(default_factory=dict)


class TaskDraft(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    topic: str = Field(min_length=2, max_length=100)
    expected_minutes: int
    objective: str
    curriculum_version: str = "legacy"
    track_key: str = "legacy"
    stage_key: str = "legacy"
    node_key: str = "legacy"
    prerequisites: list[str] = Field(default_factory=list)
    instructions: list[str | TaskStep] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    submission_kinds: list[str] = Field(min_length=1)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_checks: list[AcceptanceCheck] = Field(default_factory=list)
    rubric: list[RubricCriterionDraft] = Field(min_length=1)
    remediation_hint: str = ""
    is_remediation: bool = False
    task_kind: Literal["theory", "coding", "debugging", "design", "review", "algorithm"] = "coding"
    learning_objectives: list[str] = Field(default_factory=list)
    theory_brief: str = ""
    problem_statement: str = Field(default="", min_length=20, max_length=4_000)
    constraints: list[str] = Field(default_factory=list)
    starter_context: str = ""
    hints: list[str] = Field(default_factory=list)
    solution_outline: str = ""
    replaces_task_id: str | None = None
    regeneration_reason: str = ""
    generation_source: Literal["ai", "rules", "legacy"] = "legacy"


class TaskPolicy:
    @staticmethod
    def validate(
        task: TaskDraft, recent_topics: list[tuple[str, datetime]], now: datetime | None = None
    ) -> TaskDraft:
        if not 30 <= task.expected_minutes <= 45:
            raise ValueError("expected_minutes must be between 30 and 45")
        if task.curriculum_version != "legacy":
            if len(task.learning_objectives) < 2:
                raise ValueError("curriculum task requires theory and practice objectives")
            if len(task.theory_brief.strip()) < 20:
                raise ValueError("curriculum task requires a concrete theory brief")
            if len(task.problem_statement.strip()) < 30:
                raise ValueError("curriculum task requires an explicit problem statement")
            if not task.constraints:
                raise ValueError("curriculum task requires constraints")
            if len(task.hints) != 3:
                raise ValueError("curriculum task requires exactly three hint levels")
            if len({item.strip().casefold() for item in task.hints}) != 3:
                raise ValueError("curriculum task requires three distinct hint levels")
            if any(len(item.strip()) < 12 for item in task.hints):
                raise ValueError("curriculum hints must contain actionable guidance")
            if len(task.solution_outline.strip()) < 20:
                raise ValueError("curriculum task requires a solution outline")
            if not task.deliverables:
                raise ValueError("curriculum task requires a deliverable")
            if len(task.acceptance_checks) < 2:
                raise ValueError("curriculum task requires at least two acceptance checks")
            if not any(item.critical for item in task.rubric):
                raise ValueError("curriculum task requires a critical rubric criterion")
            if any(set(item.score_anchors) != {"0", "1", "2", "3", "4"} for item in task.rubric):
                raise ValueError("curriculum task requires complete score anchors")
            if any(isinstance(item, str) for item in task.instructions):
                raise ValueError("curriculum task requires structured steps")
            step_minutes = sum(
                item.minutes for item in task.instructions if isinstance(item, TaskStep)
            )
            if step_minutes != task.expected_minutes:
                raise ValueError("step minutes must equal expected_minutes")
        current = now or datetime.now(UTC)
        cutoff = current - timedelta(days=14)
        repeated = any(
            topic.casefold() == task.topic.casefold() and created_at >= cutoff
            for topic, created_at in recent_topics
        )
        if repeated and not task.is_remediation and task.replaces_task_id is None:
            raise ValueError("topic cannot repeat within 14 days")
        return task
