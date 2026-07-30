from datetime import UTC, datetime, timedelta

import pytest

from techgrowth_api.domain.tasks import TaskDraft, TaskPolicy


def draft(topic: str = "RAG evaluation", minutes: int = 35) -> TaskDraft:
    return TaskDraft(
        title="Build a retrieval evaluator",
        topic=topic,
        expected_minutes=minutes,
        objective="Measure grounded answer quality",
        instructions=["Create fixtures", "Run the evaluator"],
        source_ids=["source-1"],
        submission_kinds=["commit"],
        rubric=[{"key": "correctness", "label": "Correctness", "critical": True}],
    )


def test_daily_task_must_fit_thirty_to_forty_five_minutes() -> None:
    with pytest.raises(ValueError, match="30 and 45"):
        TaskPolicy.validate(draft(minutes=50), [])


def test_topic_cannot_repeat_within_fourteen_days() -> None:
    recent = [("RAG evaluation", datetime.now(UTC) - timedelta(days=3))]

    with pytest.raises(ValueError, match="14 days"):
        TaskPolicy.validate(draft(), recent)


def test_remediation_can_repeat_recent_topic() -> None:
    recent = [("RAG evaluation", datetime.now(UTC) - timedelta(days=1))]
    item = draft()
    item.is_remediation = True

    assert TaskPolicy.validate(item, recent) is item
