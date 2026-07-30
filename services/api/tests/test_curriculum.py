from techgrowth_api.domain.curriculum import CURRICULUM, CurriculumSelector


def test_catalog_contains_four_weighted_tracks_and_forty_eight_nodes() -> None:
    assert {track.key: track.weight for track in CURRICULUM.tracks} == {
        "ai": 0.40,
        "backend": 0.25,
        "quality": 0.20,
        "devops": 0.15,
    }
    assert sum(len(track.nodes) for track in CURRICULUM.tracks) == 48


def test_selector_uses_weighted_track_deficit() -> None:
    history = ["ai"] * 4 + ["backend"] * 3 + ["quality"] * 2

    selected = CurriculumSelector(CURRICULUM).select(history, completed=set())

    assert selected.track_key == "devops"


def test_selector_respects_prerequisites() -> None:
    selected = CurriculumSelector(CURRICULUM).select([], completed=set())

    assert selected.track_key == "ai"
    assert selected.prerequisites == ()


def test_selector_advances_after_evidence_completes_prerequisite() -> None:
    first = CURRICULUM.track("ai").nodes[0]

    selected = CurriculumSelector(CURRICULUM).select(
        ["backend", "quality", "devops"], completed={first.key}
    )

    assert selected.track_key == "ai"
    assert selected.key == CURRICULUM.track("ai").nodes[1].key


def test_selector_prioritizes_remediation() -> None:
    remediation = CURRICULUM.track("backend").nodes[4]

    selected = CurriculumSelector(CURRICULUM).select([], completed=set(), remediation=remediation)

    assert selected is remediation
