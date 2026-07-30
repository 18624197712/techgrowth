from datetime import UTC, datetime, timedelta

import pytest

from techgrowth_api.domain.growth import Evidence, EvidencePolicy, RubricScore
from techgrowth_api.domain.types import SkillLevel


def test_review_pass_requires_average_three_and_no_critical_score_below_two() -> None:
    passing = [
        RubricScore("correctness", 3, critical=True),
        RubricScore("testing", 3, critical=False),
    ]
    critical_failure = [
        RubricScore("correctness", 1, critical=True),
        RubricScore("testing", 4, critical=False),
    ]

    assert EvidencePolicy.review_passes(passing) is True
    assert EvidencePolicy.review_passes(critical_failure) is False


def test_skill_level_only_uses_accepted_evidence() -> None:
    now = datetime.now(UTC)
    evidence = [
        Evidence("e1", accepted=True, repo_linked=False, score=3.0, created_at=now),
        Evidence("e2", accepted=False, repo_linked=True, score=4.0, created_at=now),
    ]

    assert EvidencePolicy.level_for(evidence) is SkillLevel.PRACTICING


def test_applied_requires_three_accepted_items_and_repository_evidence() -> None:
    now = datetime.now(UTC)
    evidence = [
        Evidence("e1", True, False, 3.0, now - timedelta(days=15)),
        Evidence("e2", True, True, 3.2, now - timedelta(days=7)),
        Evidence("e3", True, False, 3.4, now),
    ]

    assert EvidencePolicy.level_for(evidence) is SkillLevel.APPLIED


def test_empty_rubric_is_rejected() -> None:
    with pytest.raises(ValueError, match="rubric"):
        EvidencePolicy.review_passes([])
