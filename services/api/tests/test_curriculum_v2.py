from datetime import date

import pytest

from techgrowth_api.domain.curriculum import CURRICULUM
from techgrowth_api.models import LearningTaskRecord
from techgrowth_api.services.curriculum import CurriculumService


def test_catalog_exposes_four_main_tracks_and_algorithm_track() -> None:
    assert [track.key for track in CURRICULUM.tracks] == [
        "java",
        "python_ai",
        "go",
        "node_ts",
        "algorithms",
    ]
    assert CURRICULUM.version == "v2"
    assert all(
        {node.stage_key for node in track.nodes}
        == {"foundation", "practice", "production", "architecture"}
        for track in CURRICULUM.tracks
    )
    assert all(
        len(CURRICULUM.track(key).nodes) == 12 for key in {"java", "python_ai", "go", "node_ts"}
    )
    assert len(CURRICULUM.track("algorithms").nodes) >= 24


def test_curriculum_state_has_one_active_primary_track(client) -> None:
    service = CurriculumService(client.app.state.database.session_factory)

    state = service.state()

    assert state.active_track_key == "java"
    assert state.algorithm_days_per_week == 2
    assert state.catalog_version == "v2"


def test_switching_tracks_preserves_existing_progress(client) -> None:
    factory = client.app.state.database.session_factory
    first_java = CURRICULUM.track("java").nodes[0]
    with factory() as db:
        db.add(
            LearningTaskRecord(
                title="Java 基础证据",
                topic="Java",
                skill_name="Java",
                expected_minutes=35,
                objective=first_java.objective,
                curriculum_version="v2",
                track_key="java",
                stage_key=first_java.stage_key,
                node_key=first_java.key,
                prerequisites=[],
                instructions=[],
                source_ids=[],
                submission_kinds=["answer"],
                deliverables=[],
                acceptance_checks=[],
                rubric=[],
                status="passed",
            )
        )
        db.commit()

    service = CurriculumService(factory)
    service.switch_track("go")
    service.switch_track("java")
    service.set_algorithm_frequency(0)

    java = next(item for item in service.progress() if item.track_key == "java")
    assert java.completed_nodes == 1
    assert service.next_node(date(2026, 7, 31)).key == CURRICULUM.track("java").nodes[1].key


@pytest.mark.parametrize("value", [-1, 8])
def test_algorithm_frequency_rejects_values_outside_week(value, client) -> None:
    service = CurriculumService(client.app.state.database.session_factory)

    with pytest.raises(ValueError, match="0 到 7"):
        service.set_algorithm_frequency(value)
