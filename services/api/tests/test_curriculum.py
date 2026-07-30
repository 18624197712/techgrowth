from techgrowth_api.domain.curriculum import LEGACY_CURRICULUM, CurriculumSelector


def test_legacy_catalog_remains_available_for_existing_tasks() -> None:
    assert {track.key: track.weight for track in LEGACY_CURRICULUM.tracks} == {
        "ai": 0.40,
        "backend": 0.25,
        "quality": 0.20,
        "devops": 0.15,
    }
    assert sum(len(track.nodes) for track in LEGACY_CURRICULUM.tracks) == 48


def test_selector_uses_weighted_track_deficit() -> None:
    history = ["ai"] * 4 + ["backend"] * 3 + ["quality"] * 2

    selected = CurriculumSelector(LEGACY_CURRICULUM).select(history, completed=set())

    assert selected.track_key == "devops"


def test_selector_respects_prerequisites() -> None:
    selected = CurriculumSelector(LEGACY_CURRICULUM).select([], completed=set())

    assert selected.track_key == "ai"
    assert selected.prerequisites == ()


def test_selector_advances_after_evidence_completes_prerequisite() -> None:
    first = LEGACY_CURRICULUM.track("ai").nodes[0]

    selected = CurriculumSelector(LEGACY_CURRICULUM).select(
        ["backend", "quality", "devops"], completed={first.key}
    )

    assert selected.track_key == "ai"
    assert selected.key == LEGACY_CURRICULUM.track("ai").nodes[1].key


def test_selector_prioritizes_remediation() -> None:
    remediation = LEGACY_CURRICULUM.track("backend").nodes[4]

    selected = CurriculumSelector(LEGACY_CURRICULUM).select(
        [], completed=set(), remediation=remediation
    )

    assert selected is remediation
