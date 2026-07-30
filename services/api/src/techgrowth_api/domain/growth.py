from dataclasses import dataclass
from datetime import datetime

from .types import SkillLevel


@dataclass(frozen=True, slots=True)
class RubricScore:
    key: str
    score: float
    critical: bool = False


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    accepted: bool
    repo_linked: bool
    score: float
    created_at: datetime


class EvidencePolicy:
    @staticmethod
    def review_passes(scores: list[RubricScore]) -> bool:
        if not scores:
            raise ValueError("rubric scores cannot be empty")
        average = sum(item.score for item in scores) / len(scores)
        critical_ok = all(item.score >= 2 for item in scores if item.critical)
        return average >= 3 and critical_ok

    @staticmethod
    def level_for(evidence: list[Evidence]) -> SkillLevel:
        accepted = sorted(
            (item for item in evidence if item.accepted), key=lambda item: item.created_at
        )
        if not accepted:
            return SkillLevel.DISCOVERING
        if len(accepted) < 3 or not any(item.repo_linked for item in accepted):
            return SkillLevel.PRACTICING
        repo_evidence = [item for item in accepted if item.repo_linked]
        recent_scores = [item.score for item in accepted[-3:]]
        if len(repo_evidence) >= 5 and sum(recent_scores) / len(recent_scores) >= 3.5:
            return SkillLevel.PROFICIENT
        return SkillLevel.APPLIED
