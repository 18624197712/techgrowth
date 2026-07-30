import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..crypto import token_hash
from ..dependencies import csrf_user, current_user
from ..models import (
    LearningTaskRecord,
    PushSubscriptionRecord,
    ReviewRecord,
    SkillEvidenceRecord,
    SkillProfileRecord,
    SubmissionRecord,
    User,
    WeeklyReviewRecord,
)
from ..schemas import ChatRequest, DeleteDataRequest, PushSubscriptionRequest

router = APIRouter(tags=["system"])


@router.post("/weekly-reviews/generate", status_code=status.HTTP_201_CREATED)
async def generate_weekly(request: Request, _: User = Depends(csrf_user)) -> dict:
    item = request.app.state.services.weekly.generate()
    await request.app.state.services.notifications.dispatch(
        "weekly_review",
        "TechGrowth 周复盘已生成",
        f"https://{request.app.state.settings.app_domain}",
        sensitive_body=item.summary,
    )
    return {
        "id": item.id,
        "summary": item.summary,
        "evidence_ids": item.evidence_ids,
        "next_focus": item.next_focus,
        "created_at": item.created_at,
    }


@router.get("/export")
def export_data(request: Request, _: User = Depends(current_user)) -> dict:
    with request.app.state.database.session_factory() as db:
        skills = db.scalars(select(SkillProfileRecord)).all()
        evidence = db.scalars(select(SkillEvidenceRecord)).all()
        tasks = db.scalars(select(LearningTaskRecord)).all()
        submissions = db.scalars(select(SubmissionRecord)).all()
        reviews = db.scalars(select(ReviewRecord)).all()
        return {
            "version": 1,
            "skills": [{"id": item.id, "name": item.name, "level": item.level} for item in skills],
            "evidence": [
                {
                    "id": item.id,
                    "skill_id": item.skill_id,
                    "score": item.score,
                    "summary": item.summary,
                }
                for item in evidence
            ],
            "tasks": [
                {"id": item.id, "title": item.title, "status": item.status} for item in tasks
            ],
            "submissions": [
                {"id": item.id, "task_id": item.task_id, "summary": item.summary}
                for item in submissions
            ],
            "reviews": [
                {"id": item.id, "submission_id": item.submission_id, "passed": item.passed}
                for item in reviews
            ],
        }


@router.post("/chat/stream")
def chat_stream(
    payload: ChatRequest, request: Request, _: User = Depends(csrf_user)
) -> StreamingResponse:
    async def events():
        chat_configured = request.app.state.services.settings.provider_status()["chat"][
            "api_key_configured"
        ]
        message = (
            "先对照当前任务的 rubric 找到最低分项，再补一条可验证证据。"
            if not chat_configured
            else "我已收到问题。请基于当前任务证据继续分析。"
        )
        yield f"event: token\ndata: {json.dumps({'text': message}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/notifications/push-subscriptions", status_code=status.HTTP_201_CREATED)
def save_push_subscription(
    payload: PushSubscriptionRequest,
    request: Request,
    _: User = Depends(csrf_user),
) -> dict:
    endpoint = str(payload.endpoint)
    encrypted = request.app.state.services.auth.cipher.encrypt(payload.model_dump_json())
    with request.app.state.database.session_factory() as db:
        item = db.scalar(
            select(PushSubscriptionRecord).where(
                PushSubscriptionRecord.endpoint_hash == token_hash(endpoint)
            )
        )
        if item:
            item.subscription_enc = encrypted
        else:
            item = PushSubscriptionRecord(
                endpoint_hash=token_hash(endpoint), subscription_enc=encrypted
            )
            db.add(item)
        db.commit()
        return {"id": item.id, "ok": True}


@router.delete("/data")
def delete_growth_data(
    payload: DeleteDataRequest, request: Request, _: User = Depends(csrf_user)
) -> dict:
    if payload.confirmation != "DELETE MY GROWTH DATA":
        raise HTTPException(400, "Confirmation phrase does not match")
    with request.app.state.database.session_factory() as db:
        for model in (
            ReviewRecord,
            SubmissionRecord,
            SkillEvidenceRecord,
            LearningTaskRecord,
            SkillProfileRecord,
            WeeklyReviewRecord,
        ):
            db.query(model).delete()
        db.commit()
    return {"ok": True}
