"""Email login use cases backed by Redis and PostgreSQL."""

import secrets
from datetime import datetime, timezone

import httpx

from app.core.config import resend_settings
from app.core.exceptions import BusinessError
from app.core.error_codes import ErrorCode
from app.core.security import (
    code_digest,
    new_email_code,
    new_session_token,
)
from app.db.session import session_scope
from app.models.user import User
from app.repositories import auth_redis_repository, user_repository
from app.schemas.user import LoginRequest, UserDTO
from app.services import email_service


def normalize_email(email: str) -> str:
    return email.strip().lower()


def send_login_code(email: str) -> None:
    email = normalize_email(email)
    api_key, sender = resend_settings()
    if not api_key or not sender:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "邮件服务尚未配置")

    code = new_email_code()
    salt = secrets.token_bytes(16)
    digest = code_digest(code, salt)
    should_send = auth_redis_repository.issue_login_code(email, salt, digest)
    if not should_send:
        return

    try:
        email_service.send_login_email(email, code)
    except (RuntimeError, httpx.HTTPError) as error:
        auth_redis_repository.remove_login_code_if_matches(email, digest)
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "验证码发送失败，请稍后重试") from error


def to_user_dto(user: User) -> UserDTO:
    return UserDTO(
        id=str(user.id),
        email=str(user.email),
        role=str(user.role).upper(),
        emailVerified=bool(user.email_verified),
        name=user.name,
        avatarUrl=user.avatar_url,
        signUpProvider=user.sign_up_provider,
        lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
    )


def login_user(body: LoginRequest, ip_address: str | None, user_agent: str) -> tuple[UserDTO, str]:
    email = normalize_email(str(body.email))
    now = datetime.now(timezone.utc)
    result: UserDTO | None = None

    if not auth_redis_repository.consume_login_code(email, body.code):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "验证码错误或已过期，或账号不可用")

    user_id: int | None = None
    with session_scope() as db:
        user = user_repository.get_user_by_email_for_update(db, email)
        if user is None:
            user = user_repository.create_user_if_missing(
                db, email, body.locale, body.time_zone, body.country,
            )
        if user.is_active and not user.is_deleted:
            user.email_verified = True
            user.last_login_at = now
            user_repository.record_login(db, user.id, ip_address, user_agent)
            user_id = user.id
            result = to_user_dto(user)

    if result is None or user_id is None:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "验证码错误或已过期，或账号不可用")
    token = new_session_token()
    auth_redis_repository.create_web_session(token, user_id)
    return result, token


def current_user(token: str | None) -> UserDTO:
    if not token:
        raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
    user_id = auth_redis_repository.get_session_user_id(token)
    if user_id is None:
        raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
    with session_scope() as db:
        user = user_repository.get_active_user_by_id(db, user_id)
        if user is None:
            auth_redis_repository.revoke_web_session(token)
            raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
        return to_user_dto(user)


def update_current_user_name(user_id: int, name: str) -> UserDTO:
    normalized = name.strip()
    if not normalized or len(normalized) > 80:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "昵称无效")
    with session_scope() as db:
        user = user_repository.get_active_user_by_id(db, user_id)
        if user is None:
            raise BusinessError(404, ErrorCode.NOT_FOUND, "用户不存在")
        user.name = normalized
        db.flush()
        return to_user_dto(user)


def logout_user(token: str | None) -> None:
    if token:
        auth_redis_repository.revoke_web_session(token)
