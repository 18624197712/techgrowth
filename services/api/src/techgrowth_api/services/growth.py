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

    def __init__(self, session_factory, curriculum=None) -> None:
        self.session_factory = session_factory
        self.curriculum = curriculum

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
                **draft.model_dump(mode="json"),
            )
            db.add(task)
            db.commit()
            return task

    def has_task_today(self) -> bool:
        return self.today_task() is not None

    def today_task(self) -> LearningTaskRecord | None:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            latest = db.scalar(
                select(LearningTaskRecord).order_by(LearningTaskRecord.created_at.desc()).limit(1)
            )
            if latest and self._aware(latest.created_at).date() == now.date():
                db.expunge(latest)
                return latest
            return None

    def next_curriculum_node(self):
        if self.curriculum is not None:
            return self.curriculum.next_node(datetime.now(UTC).date())
        with self.session_factory() as db:
            tasks = list(
                db.scalars(
                    select(LearningTaskRecord).order_by(LearningTaskRecord.created_at.asc())
                ).all()
            )
        curriculum_tasks = [item for item in tasks if item.node_key != "legacy"]
        completed = {item.node_key for item in curriculum_tasks if item.status == "passed"}
        remediation_task = next(
            (item for item in reversed(curriculum_tasks) if item.status == "remediation"), None
        )
        from ..domain.curriculum import LEGACY_CURRICULUM, CurriculumSelector

        remediation = (
            LEGACY_CURRICULUM.node(remediation_task.node_key)
            if remediation_task is not None
            else None
        )
        recent_tracks = [item.track_key for item in curriculum_tasks if not item.is_remediation][
            -10:
        ]
        return CurriculumSelector(LEGACY_CURRICULUM).select(recent_tracks, completed, remediation)

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
                **draft.model_dump(mode="json"),
            )
            db.add(task)
            db.commit()
            return task

    def get_task(self, task_id: str) -> LearningTaskRecord | None:
        with self.session_factory() as db:
            task = db.get(LearningTaskRecord, task_id)
            if task:
                db.expunge(task)
            return task

    def reveal_hint(self, task_id: str, level: int) -> LearningTaskRecord:
        if level not in {1, 2, 3}:
            raise ValueError("提示级别必须是 1、2 或 3")
        with self.session_factory() as db:
            task = db.get(LearningTaskRecord, task_id)
            if task is None:
                raise LookupError("Task not found")
            self._repair_guidance(task)
            if level > len(task.hints):
                raise ValueError("该任务没有对应提示")
            task.revealed_hint_level = max(task.revealed_hint_level, level)
            db.commit()
            db.expunge(task)
            return task

    def reveal_solution(self, task_id: str) -> LearningTaskRecord:
        with self.session_factory() as db:
            task = db.get(LearningTaskRecord, task_id)
            if task is None:
                raise LookupError("Task not found")
            self._repair_guidance(task)
            task.solution_revealed_at = datetime.now(UTC)
            db.commit()
            db.expunge(task)
            return task

    def find_regeneration(self, key: str) -> LearningTaskRecord | None:
        with self.session_factory() as db:
            task = db.scalar(
                select(LearningTaskRecord).where(LearningTaskRecord.regeneration_key == key)
            )
            if task is not None:
                db.expunge(task)
            return task

    def replace_task(
        self,
        task_id: str,
        draft: TaskDraft,
        skill: str,
        idempotency_key: str,
    ) -> LearningTaskRecord:
        with self.session_factory() as db:
            existing = db.scalar(
                select(LearningTaskRecord).where(
                    LearningTaskRecord.regeneration_key == idempotency_key
                )
            )
            if existing is not None:
                db.expunge(existing)
                return existing
            task = db.get(LearningTaskRecord, task_id)
            if task is None:
                raise LookupError("Task not found")
            submitted = db.scalar(
                select(SubmissionRecord.id).where(SubmissionRecord.task_id == task_id).limit(1)
            )
            if submitted is not None or task.status not in {"ready", "open"}:
                raise ValueError("已提交或已完成的任务不能重新出题")
            replacement = LearningTaskRecord(
                skill_name=skill,
                status="ready",
                regeneration_key=idempotency_key,
                **draft.model_dump(mode="json"),
            )
            task.status = "replaced"
            db.add(replacement)
            db.commit()
            db.expunge(replacement)
            return replacement

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

    @staticmethod
    def _repair_guidance(task: LearningTaskRecord) -> None:
        if len(task.hints) == 3 and len(task.solution_outline.strip()) >= 20:
            return
        from ..domain.curriculum import CURRICULUM
        from ..workflows import build_curriculum_fallback

        try:
            node = CURRICULUM.node(task.node_key)
        except StopIteration as exc:
            raise ValueError("该历史任务缺少可恢复的课程提示，请重新出题") from exc
        fallback = build_curriculum_fallback(node, task.source_ids or ["curriculum-v2"])
        task.hints = fallback.hints
        task.solution_outline = fallback.solution_outline
        task.generation_source = "rules"
