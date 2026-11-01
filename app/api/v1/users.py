"""Authenticated user profile endpoint consumed by the Web auth gate."""

from fastapi import APIRouter, Request

from app.core.responses import ok
from app.core.security import COOKIE_NAME
from app.services.user_service import current_user

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/get/login")
def get_login_user(request: Request) -> dict[str, object]:
    return ok(current_user(request.cookies.get(COOKIE_NAME)).model_dump())
