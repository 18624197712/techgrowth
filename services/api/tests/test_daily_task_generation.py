from sqlalchemy import select

from techgrowth_api.domain.curriculum import CURRICULUM
from techgrowth_api.models import LearningTaskRecord


def test_growth_service_advances_after_curriculum_task_passes(client) -> None:
    growth = client.app.state.services.growth
    for track in CURRICULUM.tracks:
        first = track.nodes[0]
        draft = client.app.state.services.daily_tasks.fallback_for(first, ["source-1"])
        saved = growth.save_draft(draft, first.title)
        with client.app.state.database.session_factory() as db:
            task = db.scalar(select(LearningTaskRecord).where(LearningTaskRecord.id == saved.id))
            task.status = "passed"
            db.commit()

    selected = growth.next_curriculum_node()

    assert selected.key == CURRICULUM.track("ai").nodes[1].key


def test_growth_service_prioritizes_curriculum_remediation(client) -> None:
    growth = client.app.state.services.growth
    node = CURRICULUM.track("backend").nodes[0]
    draft = client.app.state.services.daily_tasks.fallback_for(node, ["source-1"])
    draft.is_remediation = True
    saved = growth.save_draft(draft, node.title)
    with client.app.state.database.session_factory() as db:
        task = db.scalar(select(LearningTaskRecord).where(LearningTaskRecord.id == saved.id))
        task.status = "remediation"
        db.commit()

    assert growth.next_curriculum_node().key == node.key


def test_manual_generation_uses_shared_curriculum_service(authenticated_client) -> None:
    client, csrf = authenticated_client

    response = client.post(
        "/api/v1/tasks/generate",
        headers={"X-CSRF-Token": csrf},
        json={"topic": "random topic", "skill": "random skill"},
    )

    assert response.status_code == 201
    task = response.json()
    assert task["curriculum_version"] == "v1"
    assert task["track_key"] == "ai"
    assert task["node_key"] == "ai-foundation-model-io"
    assert len(task["acceptance_checks"]) >= 2
