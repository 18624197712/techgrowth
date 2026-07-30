from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..dependencies import current_user
from ..models import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _view(request: Request, range_key: str, reader: Callable) -> dict:
    try:
        return reader(range_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/overview")
def overview(
    request: Request,
    range_key: str = Query(default="30d", alias="range"),
    _: User = Depends(current_user),
) -> dict:
    return _view(request, range_key, request.app.state.services.analytics.overview)


@router.get("/learning")
def learning(
    request: Request,
    range_key: str = Query(default="30d", alias="range"),
    _: User = Depends(current_user),
) -> dict:
    return _view(request, range_key, request.app.state.services.analytics.learning)


@router.get("/radar")
def radar(
    request: Request,
    range_key: str = Query(default="30d", alias="range"),
    _: User = Depends(current_user),
) -> dict:
    return _view(request, range_key, request.app.state.services.analytics.radar)


@router.get("/repositories")
def repositories(
    request: Request,
    range_key: str = Query(default="30d", alias="range"),
    _: User = Depends(current_user),
) -> dict:
    return _view(request, range_key, request.app.state.services.analytics.repositories)


@router.get("/ai-runs")
def ai_runs(
    request: Request,
    range_key: str = Query(default="30d", alias="range"),
    _: User = Depends(current_user),
) -> dict:
    return _view(request, range_key, request.app.state.services.analytics.ai_runs)
