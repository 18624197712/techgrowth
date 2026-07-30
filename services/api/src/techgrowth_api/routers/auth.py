from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from ..schemas import LoginRequest, TotpRequest
from ..services.auth import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, token: str, secure: bool) -> None:
    response.set_cookie(
        "tg_session",
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    try:
        result = request.app.state.services.auth.login(
            payload.email, payload.password, request.client.host if request.client else "unknown"
        )
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    set_session_cookie(response, result.token, request.app.state.settings.secure_cookies)
    return {"next": result.next_step}


@router.get("/totp/setup")
def totp_setup(request: Request, tg_session: str = Cookie(default="")) -> dict:
    try:
        return request.app.state.services.auth.totp_setup(tg_session)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/totp/confirm")
def totp_confirm(
    payload: TotpRequest, request: Request, tg_session: str = Cookie(default="")
) -> dict:
    try:
        csrf, recovery = request.app.state.services.auth.confirm_totp(tg_session, payload.code)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"csrf_token": csrf, "recovery_codes": recovery}


@router.post("/totp/verify")
def totp_verify(
    payload: TotpRequest, request: Request, tg_session: str = Cookie(default="")
) -> dict:
    try:
        csrf, _ = request.app.state.services.auth.confirm_totp(tg_session, payload.code)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"csrf_token": csrf}


@router.get("/me")
def me(request: Request, tg_session: str = Cookie(default="")) -> dict:
    try:
        _, user = request.app.state.services.auth.authenticated(tg_session)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"id": user.id, "email": user.email, "totp_enabled": user.totp_enabled}


@router.post("/logout")
def logout(request: Request, response: Response, tg_session: str = Cookie(default="")) -> dict:
    request.app.state.services.auth.logout(tg_session)
    response.delete_cookie("tg_session", path="/")
    return {"ok": True}
