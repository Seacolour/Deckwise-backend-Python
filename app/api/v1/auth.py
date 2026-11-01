"""Email code login and logout endpoints consumed by the existing Web app."""

from fastapi import APIRouter, Request, Response

from app.core.config import secure_session_cookie
from app.core.responses import ok
from app.core.security import COOKIE_NAME, SESSION_LIFETIME
from app.schemas.user import EmailCodeRequest, LoginRequest
from app.services.user_service import login_user, logout_user, send_login_code

router = APIRouter(prefix="/api/user", tags=["auth"])


@router.post("/login/email-code")
def send_login_email_code(body: EmailCodeRequest) -> dict[str, object]:
    send_login_code(str(body.email))
    return ok(True)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    user, token = login_user(
        body,
        request.client.host if request.client else None,
        request.headers.get("user-agent", ""),
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
        httponly=True,
        secure=secure_session_cookie(),
        samesite="lax",
    )
    return ok({"user": user.model_dump()})


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, object]:
    logout_user(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return ok(True)
