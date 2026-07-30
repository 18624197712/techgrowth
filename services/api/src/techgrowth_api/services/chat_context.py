from sqlalchemy import select

from ..domain.curriculum import CURRICULUM
from ..models import (
    LearningTaskRecord,
    RadarItemRecord,
    ReviewRecord,
    SkillProfileRecord,
    SubmissionRecord,
)


class ChatContextService:
    PAGE_KEYS = {"view", "task_id", "radar_item_id", "submission_id"}

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def build(self, intent: str, page_context: dict) -> dict:
        page = {
            key: str(value)[:200]
            for key, value in page_context.items()
            if key in self.PAGE_KEYS and isinstance(value, (str, int))
        }
        if intent == "task_coaching":
            return {"page": page, "task": self._task(page.get("task_id"))}
        if intent == "submission_improvement":
            return {"page": page, **self._submission(page.get("submission_id"))}
        if intent == "growth_planning":
            return {"page": page, **self._growth()}
        if intent == "radar_to_task":
            return {"page": page, "radar": self._radar(page.get("radar_item_id"))}
        return {"page": page}

    def _task(self, task_id: str | None) -> dict | None:
        with self.session_factory() as db:
            task = db.get(LearningTaskRecord, task_id) if task_id else None
            if task is None:
                task = db.scalar(
                    select(LearningTaskRecord)
                    .order_by(LearningTaskRecord.created_at.desc())
                    .limit(1)
                )
            if task is None:
                return None
            return {
                "id": task.id,
                "title": task.title,
                "objective": task.objective,
                "track_key": task.track_key,
                "stage_key": task.stage_key,
                "node_key": task.node_key,
                "prerequisites": task.prerequisites,
                "instructions": task.instructions,
                "deliverables": task.deliverables,
                "acceptance_checks": task.acceptance_checks,
                "rubric": task.rubric,
                "status": task.status,
            }

    def _submission(self, submission_id: str | None) -> dict:
        with self.session_factory() as db:
            submission = db.get(SubmissionRecord, submission_id) if submission_id else None
            if submission is None:
                submission = db.scalar(
                    select(SubmissionRecord).order_by(SubmissionRecord.created_at.desc()).limit(1)
                )
            if submission is None:
                return {"submission": None, "review": None}
            review = db.scalar(
                select(ReviewRecord).where(ReviewRecord.submission_id == submission.id)
            )
            return {
                "submission": {
                    "id": submission.id,
                    "task_id": submission.task_id,
                    "summary": submission.summary[:4000],
                    "artifact_kind": submission.artifact_kind,
                    "artifact_reference": submission.artifact_reference[:500],
                    "self_scores": submission.self_scores,
                },
                "review": (
                    {
                        "passed": review.passed,
                        "overall_score": review.overall_score,
                        "criterion_scores": review.criterion_scores,
                        "feedback": review.feedback[:4000],
                    }
                    if review
                    else None
                ),
            }

    def _growth(self) -> dict:
        with self.session_factory() as db:
            skills = list(
                db.scalars(
                    select(SkillProfileRecord)
                    .order_by(SkillProfileRecord.updated_at.desc())
                    .limit(20)
                ).all()
            )
            tasks = list(
                db.scalars(
                    select(LearningTaskRecord).where(
                        LearningTaskRecord.curriculum_version != "legacy"
                    )
                ).all()
            )
        completed = {task.node_key for task in tasks if task.status == "passed"}
        return {
            "skills": [
                {"name": item.name, "level": item.level, "updated_at": item.updated_at}
                for item in skills
            ],
            "curriculum_progress": [
                {
                    "track_key": track.key,
                    "completed": sum(node.key in completed for node in track.nodes),
                    "total": len(track.nodes),
                }
                for track in CURRICULUM.tracks
            ],
        }

    def _radar(self, radar_id: str | None) -> dict | None:
        with self.session_factory() as db:
            item = db.get(RadarItemRecord, radar_id) if radar_id else None
            if item is None:
                item = db.scalar(
                    select(RadarItemRecord).order_by(RadarItemRecord.relevance.desc()).limit(1)
                )
            if item is None:
                return None
            return {
                "id": item.id,
                "title": item.title,
                "summary": item.summary[:4000],
                "source_url": item.source_url,
                "source_name": item.source_name,
                "topic": item.topic,
                "credibility": item.credibility,
                "relevance": item.relevance,
            }
