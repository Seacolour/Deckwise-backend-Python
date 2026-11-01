"""Shared HTTP authentication boundary for workspace routes."""

from fastapi import Request

from app.core.security import COOKIE_NAME
from app.services.user_service import current_user


def current_user_id(request: Request) -> int:
    return int(current_user(request.cookies.get(COOKIE_NAME)).id)
