import pytest
from pydantic import ValidationError

from techgrowth_api.domain.curriculum import CURRICULUM
from techgrowth_api.domain.tasks import TaskPolicy
from techgrowth_api.workflows import build_curriculum_fallback


def test_curriculum_fallback_contains_complete_learning_contract() -> None:
    node = CURRICULUM.track("java").nodes[0]

    task = build_curriculum_fallback(node, ["curriculum-v2"])

    assert task.curriculum_version == "v2"
    assert task.task_kind in {"theory", "coding", "debugging", "design", "review", "algorithm"}
    assert len(task.learning_objectives) >= 2
    assert len(task.theory_brief) >= 20
    assert len(task.problem_statement) >= 30
    assert task.constraints
    assert len(task.hints) == 3
    assert len(set(task.hints)) == 3
    assert len(task.solution_outline) >= 20
    assert task.generation_source == "rules"
    assert TaskPolicy.validate(task, []) is task


def test_v2_task_rejects_ambiguous_problem_statement() -> None:
    task = build_curriculum_fallback(CURRICULUM.track("go").nodes[0], ["curriculum-v2"])

    with pytest.raises(ValidationError):
        task.model_copy(update={"problem_statement": "完成练习"}).model_validate(
            {**task.model_dump(), "problem_statement": "完成练习"}
        )
