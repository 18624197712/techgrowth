from datetime import UTC, datetime

from sqlalchemy import select

from ..domain.growth import Evidence, EvidencePolicy, RubricScore
from ..domain.tasks import TaskDraft, TaskPolicy
from ..models import (
    LearningTaskRecord,
    ReviewRecord,
    SkillEvidenceRecord,
    SkillProfileRecord,
    SubmissionRecord,
)
from ..schemas import SubmissionRequest


class GrowthService:
    DEFAULT_RUBRIC = [
        {"key": "correctness", "label": "实现正确性", "critical": True},
        {"key": "testing", "label": "验证与测试", "critical": False},
    ]

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def generate_task(self, topic: str, skill: str) -> LearningTaskRecord:
        with self.session_factory() as db:
            recent = db.scalars(select(LearningTaskRecord)).all()
            draft = TaskDraft(
                title=f"完成一个 {topic} 的可验证实验",
                topic=topic,
                expected_minutes=35,
                objective=f"用 Python 实践 {skill}，并留下可复查证据。",
                instructions=[
                    "定义一个可验证的成功标准",
                    "实现最小实验并记录关键决策",
                    "运行验证并提交代码或结果摘要",
                ],
                source_ids=["seed-agent-engineering"],
                submission_kinds=["commit", "report", "answer"],
                rubric=self.DEFAULT_RUBRIC,
            )
            TaskPolicy.validate(
                draft, [(item.topic, self._aware(item.created_at)) for item in recent]
            )
            task = LearningTaskRecord(
                skill_name=skill,
                status="ready",
                **draft.model_dump(exclude_defaults=True),
            )
            db.add(task)
            db.commit()
            return task

    def has_task_today(self) -> bool:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            latest = db.scalar(
                select(LearningTaskRecord).order_by(LearningTaskRecord.created_at.desc()).limit(1)
            )
            return bool(latest and self._aware(latest.created_at).date() == now.date())

    def recent_topics(self) -> list[tuple[str, datetime]]:
        with self.session_factory() as db:
            return [
                (item.topic, self._aware(item.created_at))
                for item in db.scalars(select(LearningTaskRecord)).all()
            ]

    def save_draft(self, draft: TaskDraft, skill: str) -> LearningTaskRecord:
        with self.session_factory() as db:
            task = LearningTaskRecord(
                skill_name=skill,
                status="ready",
                **draft.model_dump(exclude_defaults=True),
            )
            db.add(task)
            db.commit()
            return task

    def submit(
        self, task_id: str, request: SubmissionRequest
    ) -> tuple[SubmissionRecord, ReviewRecord]:
        with self.session_factory() as db:
            task = db.get(LearningTaskRecord, task_id)
            if not task:
                raise LookupError("Task not found")
            scores = [
                RubricScore(
                    item["key"],
                    float(request.self_scores.get(item["key"], 0)),
                    bool(item.get("critical")),
                )
                for item in task.rubric
            ]
            passed = EvidencePolicy.review_passes(scores)
            average = sum(item.score for item in scores) / len(scores)
            submission = SubmissionRecord(task_id=task.id, **request.model_dump())
            db.add(submission)
            db.flush()
            review = ReviewRecord(
                submission_id=submission.id,
                passed=passed,
                overall_score=average,
                criterion_scores=[
                    {"key": item.key, "score": item.score, "critical": item.critical}
                    for item in scores
                ],
                feedback=(
                    "证据满足 rubric，可以进入下一项练习。"
                    if passed
                    else "请针对低分项补充实现或验证证据。"
                ),
            )
            db.add(review)
            task.status = "passed" if passed else "remediation"
            if passed:
                skill = db.scalar(
                    select(SkillProfileRecord).where(SkillProfileRecord.name == task.skill_name)
                )
                if not skill:
                    skill = SkillProfileRecord(name=task.skill_name)
                    db.add(skill)
                    db.flush()
                db.add(
                    SkillEvidenceRecord(
                        skill_id=skill.id,
                        submission_id=submission.id,
                        accepted=True,
                        repo_linked=request.artifact_kind in {"commit", "pull_request", "file"},
                        score=average,
                        summary=request.summary,
                    )
                )
                db.flush()
                evidence = db.scalars(
                    select(SkillEvidenceRecord).where(SkillEvidenceRecord.skill_id == skill.id)
                ).all()
                skill.level = EvidencePolicy.level_for(
                    [
                        Evidence(
                            item.id,
                            item.accepted,
                            item.repo_linked,
                            item.score,
                            self._aware(item.created_at),
                        )
                        for item in evidence
                    ]
                ).value
                skill.updated_at = datetime.now(UTC)
            db.commit()
            return submission, review

    def profile(self) -> list[dict]:
        with self.session_factory() as db:
            skills = db.scalars(select(SkillProfileRecord).order_by(SkillProfileRecord.name)).all()
            result = []
            for skill in skills:
                count = len(
                    db.scalars(
                        select(SkillEvidenceRecord).where(
                            SkillEvidenceRecord.skill_id == skill.id,
                            SkillEvidenceRecord.accepted.is_(True),
                        )
                    ).all()
                )
                result.append(
                    {
                        "id": skill.id,
                        "name": skill.name,
                        "level": skill.level,
                        "evidence_count": count,
                        "updated_at": skill.updated_at,
                    }
                )
            return result

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)
