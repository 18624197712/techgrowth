from techgrowth_api.domain.tasks import TaskDraft
from techgrowth_api.evaluation import score_task


def test_task_evaluation_requires_valid_citations_constraints_and_rubric() -> None:
    task = TaskDraft(
        title="Build an agent retry experiment",
        topic="Agent reliability",
        expected_minutes=35,
        objective="Measure bounded retry behavior",
        instructions=["Write a failing case", "Implement a bound", "Run tests"],
        source_ids=["source-1"],
        submission_kinds=["commit"],
        rubric=[
            {"key": "correctness", "label": "Correctness", "critical": True},
            {"key": "testing", "label": "Testing", "critical": False},
        ],
    )

    score = score_task(task, {"source-1"})

    assert score == {"citation_valid": True, "constraints_valid": True, "rubric_covered": True}
