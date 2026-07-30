from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..dependencies import csrf_user, current_user
from ..models import NotificationPreferenceRecord, User
from ..schemas import NotificationPreferencesRequest
from ..services.settings import ProviderSettings, ProviderSettingsValidationError

router = APIRouter(tags=["settings"])


@router.get("/setup")
def setup_status(request: Request, _: User = Depends(current_user)) -> dict:
    return {
        "provider": request.app.state.services.settings.provider_status(),
        "domain": request.app.state.settings.app_domain,
        "icp_number": request.app.state.settings.icp_number,
        "smtp_configured": bool(request.app.state.settings.smtp_host),
        "web_push_configured": bool(request.app.state.settings.vapid_public_key),
        "vapid_public_key": request.app.state.settings.vapid_public_key,
    }


@router.put("/setup/provider")
def save_provider(
    payload: ProviderSettings, request: Request, _: User = Depends(csrf_user)
) -> dict:
    try:
        request.app.state.services.settings.save_provider(payload)
    except ProviderSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return request.app.state.services.settings.provider_status()


@router.get("/notifications/preferences")
def notification_preferences(request: Request, _: User = Depends(current_user)) -> list[dict]:
    with request.app.state.database.session_factory() as db:
        items = db.scalars(
            select(NotificationPreferenceRecord).order_by(
                NotificationPreferenceRecord.channel,
                NotificationPreferenceRecord.event,
            )
        ).all()
        return [
            {"channel": item.channel, "event": item.event, "enabled": item.enabled}
            for item in items
        ]


@router.put("/notifications/preferences")
def save_notification_preferences(
    payload: NotificationPreferencesRequest,
    request: Request,
    _: User = Depends(csrf_user),
) -> list[dict]:
    with request.app.state.database.session_factory() as db:
        result = []
        for value in payload.preferences:
            item = db.scalar(
                select(NotificationPreferenceRecord).where(
                    NotificationPreferenceRecord.channel == value.channel,
                    NotificationPreferenceRecord.event == value.event,
                )
            )
            if not item:
                item = NotificationPreferenceRecord(
                    channel=value.channel, event=value.event, enabled=value.enabled
                )
                db.add(item)
            else:
                item.enabled = value.enabled
            result.append(
                {"channel": value.channel, "event": value.event, "enabled": value.enabled}
            )
        db.commit()
        return result
