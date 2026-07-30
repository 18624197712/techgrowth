from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from ..dependencies import csrf_user, current_user
from ..models import LearningTaskRecord, ReviewRecord, User, WeeklyReviewRecord
from ..schemas import SubmissionRequest, TaskGenerateRequest

router = APIRouter(tags=["growth"])


def task_dict(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "topic": task.topic,
        "skill_name": task.skill_name,
        "expected_minutes": task.expected_minutes,
        "objective": task.objective,
        "curriculum_version": task.curriculum_version,
        "track_key": task.track_key,
        "stage_key": task.stage_key,
        "node_key": task.node_key,
        "prerequisites": task.prerequisites,
        "instructions": task.instructions,
        "source_ids": task.source_ids,
        "submission_kinds": task.submission_kinds,
        "deliverables": task.deliverables,
        "acceptance_checks": task.acceptance_checks,
        "rubric": task.rubric,
        "remediation_hint": task.remediation_hint,
        "status": task.status,
        "created_at": task.created_at,
    }


@router.post("/tasks/generate", status_code=status.HTTP_201_CREATED)
def generate_task(
    payload: TaskGenerateRequest, request: Request, _: User = Depends(csrf_user)
) -> dict:
    try:
        return task_dict(
            request.app.state.services.growth.generate_task(payload.topic, payload.skill)
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/tasks/{task_id}/submissions", status_code=status.HTTP_201_CREATED)
async def submit_task(
    task_id: str,
    payload: SubmissionRequest,
    request: Request,
    _: User = Depends(csrf_user),
) -> dict:
    try:
        submission, review = request.app.state.services.growth.submit(task_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    await request.app.state.services.notifications.dispatch(
        "review_complete",
        "TechGrowth 审阅完成",
        f"https://{request.app.state.settings.app_domain}",
        sensitive_body=review.feedback,
    )
    return {
        "id": submission.id,
        "task_id": submission.task_id,
        "review": {
            "id": review.id,
            "passed": review.passed,
            "overall_score": review.overall_score,
            "criterion_scores": review.criterion_scores,
            "feedback": review.feedback,
        },
    }


@router.get("/profile")
def profile(request: Request, _: User = Depends(current_user)) -> list[dict]:
    return request.app.state.services.growth.profile()


@router.get("/radar")
def radar(request: Request, _: User = Depends(current_user)) -> list[dict]:
    return [
        {
            "id": item.id,
            "title": item.title,
            "summary": item.summary,
            "source_url": item.source_url,
            "source_name": item.source_name,
            "topic": item.topic,
            "credibility": item.credibility,
            "relevance": item.relevance,
            "relevance_reason": item.relevance_reason,
            "published_at": item.published_at,
        }
        for item in request.app.state.services.radar.list_items()
    ]


@router.get("/tasks/today")
def today_task(request: Request, _: User = Depends(current_user)) -> dict:
    with request.app.state.database.session_factory() as db:
        task = db.scalar(
            select(LearningTaskRecord).order_by(LearningTaskRecord.created_at.desc()).limit(1)
        )
        if not task:
            raise HTTPException(404, "No task is ready for today")
        return task_dict(task)


@router.get("/reviews/{submission_id}")
def review_detail(submission_id: str, request: Request, _: User = Depends(current_user)) -> dict:
    with request.app.state.database.session_factory() as db:
        review = db.scalar(select(ReviewRecord).where(ReviewRecord.submission_id == submission_id))
        if not review:
            raise HTTPException(404, "Review not found")
        return {
            "id": review.id,
            "submission_id": review.submission_id,
            "passed": review.passed,
            "overall_score": review.overall_score,
            "criterion_scores": review.criterion_scores,
            "feedback": review.feedback,
            "created_at": review.created_at,
        }


@router.get("/weekly-reviews")
def weekly_reviews(request: Request, _: User = Depends(current_user)) -> list[dict]:
    with request.app.state.database.session_factory() as db:
        items = db.scalars(
            select(WeeklyReviewRecord).order_by(WeeklyReviewRecord.created_at.desc())
        ).all()
        return [
            {
                "id": item.id,
                "summary": item.summary,
                "evidence_ids": item.evidence_ids,
                "next_focus": item.next_focus,
                "created_at": item.created_at,
            }
            for item in items
        ]
