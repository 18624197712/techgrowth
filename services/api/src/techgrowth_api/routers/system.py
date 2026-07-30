import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..chat_workflow import ChatWorkflowService
from ..crypto import token_hash
from ..dependencies import csrf_session, csrf_user, current_user
from ..integrations.model_client import ModelClient, ModelClientError
from ..integrations.provider_settings import resolve_provider_settings
from ..models import (
    AuthSession,
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
from ..services.chat_actions import ChatActionError
from ..tools import ToolRegistry
from .growth import task_dict

router = APIRouter(tags=["system"])


def sse_event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
    payload: ChatRequest,
    request: Request,
    session: AuthSession = Depends(csrf_session),
) -> StreamingResponse:
    async def events():
        try:
            settings = resolve_provider_settings(
                request.app.state.settings,
                request.app.state.services.settings.provider_values(),
            )
            factory = getattr(request.app.state, "model_client_factory", ModelClient)
            workflow = ChatWorkflowService(
                factory(settings),
                request.app.state.services.chat_context,
                ToolRegistry.from_services(request.app.state.services),
                session_id=session.id,
            )
            result = await workflow.run(payload.message, payload.page_context)
            yield sse_event(
                "intent",
                {
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "needs_action": result.needs_action,
                },
            )
            for event in result.tool_events:
                yield sse_event(
                    event["type"], {key: value for key, value in event.items() if key != "type"}
                )
            for offset in range(0, len(result.answer), 24):
                yield sse_event("token", {"text": result.answer[offset : offset + 24]})
            if result.action:
                proposal = request.app.state.services.chat_actions.create(session.id, result.action)
                yield sse_event("action_proposal", proposal)
        except ModelClientError as exc:
            yield sse_event("error", {"code": exc.code, "message": str(exc)})
        except ChatActionError as exc:
            yield sse_event("error", {"code": "action_invalid", "message": exc.message})
        except Exception:
            yield sse_event("error", {"code": "tutor_internal", "message": "导师暂时无法完成请求"})
        yield sse_event("done", {})

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/chat/actions/{action_id}/confirm")
async def confirm_chat_action(
    action_id: str,
    request: Request,
    session: AuthSession = Depends(csrf_session),
) -> dict:
    try:
        result = await request.app.state.services.chat_actions.confirm(action_id, session.id)
        return task_dict(result) if isinstance(result, LearningTaskRecord) else result
    except ChatActionError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/chat/actions/{action_id}/cancel")
def cancel_chat_action(
    action_id: str,
    request: Request,
    session: AuthSession = Depends(csrf_session),
) -> dict:
    try:
        return request.app.state.services.chat_actions.cancel(action_id, session.id)
    except ChatActionError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


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
