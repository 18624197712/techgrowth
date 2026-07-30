from fastapi import Cookie, Header, HTTPException, Request

from .models import AuthSession, User
from .services.auth import AuthError


def current_user(request: Request, tg_session: str = Cookie(default="")) -> User:
    try:
        _, user = request.app.state.services.auth.authenticated(tg_session)
        return user
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def csrf_user(
    request: Request,
    tg_session: str = Cookie(default=""),
    x_csrf_token: str = Header(default=""),
) -> User:
    try:
        return request.app.state.services.auth.validate_csrf(tg_session, x_csrf_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def csrf_session(
    request: Request,
    tg_session: str = Cookie(default=""),
    x_csrf_token: str = Header(default=""),
) -> AuthSession:
    try:
        return request.app.state.services.auth.validate_csrf_session(tg_session, x_csrf_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


async def connector_device(
    request: Request,
    authorization: str = Header(default=""),
    x_device_id: str = Header(default=""),
    x_timestamp: str = Header(default=""),
    x_nonce: str = Header(default=""),
    x_signature: str = Header(default=""),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Connector authentication failed")
    body = await request.body()
    try:
        return request.app.state.services.connector.authenticate(
            device_id=x_device_id,
            raw_token=authorization.removeprefix("Bearer "),
            method=request.method,
            path=request.url.path,
            timestamp=int(x_timestamp),
            nonce=x_nonce,
            signature=x_signature,
            body=body,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(401, str(exc)) from exc
