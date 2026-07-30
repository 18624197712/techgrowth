from datetime import UTC, datetime, timedelta

import pytest

from techgrowth_api.domain.tasks import TaskDraft, TaskPolicy


def draft(topic: str = "RAG evaluation", minutes: int = 35) -> TaskDraft:
    first_step_minutes = minutes // 2
    return TaskDraft(
        title="Build a retrieval evaluator",
        topic=topic,
        expected_minutes=minutes,
        objective="Measure grounded answer quality",
        curriculum_version="v2",
        track_key="python_ai",
        stage_key="foundation",
        node_key="python_ai-foundation-model-api",
        prerequisites=["Python virtual environment is ready"],
        instructions=[
            {
                "action": "Create deterministic request fixtures",
                "minutes": first_step_minutes,
                "expected_result": "A fixture covers one success and one failure",
            },
            {
                "action": "Run the evaluator against both fixtures",
                "minutes": minutes - first_step_minutes,
                "expected_result": "The report distinguishes the two outcomes",
            },
        ],
        source_ids=["source-1"],
        submission_kinds=["commit"],
        deliverables=["Evaluator implementation and report"],
        acceptance_checks=[
            {
                "method": "command",
                "instruction": "pytest -q",
                "expected_result": "All evaluator tests pass",
            },
            {
                "method": "inspection",
                "instruction": "Inspect the generated report",
                "expected_result": "Both fixtures have an explained score",
            },
        ],
        rubric=[
            {
                "key": "correctness",
                "label": "Correctness",
                "description": "The evaluator distinguishes grounded and ungrounded output",
                "critical": True,
                "score_anchors": {
                    "0": "No runnable evaluator",
                    "1": "Runs but does not score",
                    "2": "Scores only the happy path",
                    "3": "Scores both fixtures correctly",
                    "4": "Also explains each score",
                },
            }
        ],
        remediation_hint="Fix the lowest scoring criterion and rerun its check",
        task_kind="coding",
        learning_objectives=[
            "Explain grounded answer quality boundaries",
            "Implement and verify a deterministic evaluator",
        ],
        theory_brief=(
            "Grounded evaluation compares claims against retrieved evidence and records boundaries."
        ),
        problem_statement=(
            "Implement a deterministic evaluator for one grounded and one ungrounded answer, "
            "then produce a report that explains both scores."
        ),
        constraints=["Use fixed fixtures", "Do not call a live model"],
        hints=["Start with fixtures", "Separate scoring", "Compare both reports"],
        solution_outline=(
            "Define two fixed examples, score their supported claims independently, "
            "and assert the report."
        ),
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


def test_curriculum_task_requires_two_acceptance_checks() -> None:
    item = draft()
    item.acceptance_checks = item.acceptance_checks[:1]

    with pytest.raises(ValueError, match="acceptance checks"):
        TaskPolicy.validate(item, [])


def test_curriculum_task_step_minutes_must_match_expected_minutes() -> None:
    item = draft()
    item.instructions[0].minutes = 5

    with pytest.raises(ValueError, match="step minutes"):
        TaskPolicy.validate(item, [])


def test_curriculum_task_requires_complete_score_anchors() -> None:
    item = draft()
    item.rubric[0].score_anchors.pop("4")

    with pytest.raises(ValueError, match="score anchors"):
        TaskPolicy.validate(item, [])
