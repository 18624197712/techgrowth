from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field


class RubricCriterionDraft(BaseModel):
    key: str
    label: str
    critical: bool = False


class TaskDraft(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    topic: str = Field(min_length=2, max_length=100)
    expected_minutes: int
    objective: str
    instructions: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    submission_kinds: list[str] = Field(min_length=1)
    rubric: list[RubricCriterionDraft] = Field(min_length=1)
    is_remediation: bool = False


class TaskPolicy:
    @staticmethod
    def validate(
        task: TaskDraft, recent_topics: list[tuple[str, datetime]], now: datetime | None = None
    ) -> TaskDraft:
        if not 30 <= task.expected_minutes <= 45:
            raise ValueError("expected_minutes must be between 30 and 45")
        current = now or datetime.now(UTC)
        cutoff = current - timedelta(days=14)
        repeated = any(
            topic.casefold() == task.topic.casefold() and created_at >= cutoff
            for topic, created_at in recent_topics
        )
        if repeated and not task.is_remediation:
            raise ValueError("topic cannot repeat within 14 days")
        return task
