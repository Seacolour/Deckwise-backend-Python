"""Email login use cases; HTTP and SQL details stay at their boundaries."""

import hmac
import secrets
from datetime import datetime, timezone

import httpx

from app.core.config import resend_settings
from app.core.exceptions import BusinessError
from app.core.error_codes import ErrorCode
from app.core.security import (
    CODE_COOLDOWN,
    CODE_LIFETIME,
    MAX_CODE_ATTEMPTS,
    SESSION_LIFETIME,
    code_digest,
    new_email_code,
    new_session_token,
    token_digest,
)
from app.db.session import session_scope
from app.models.user import User
from app.repositories import user_repository
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
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        should_send = user_repository.upsert_login_code(
            db, email, salt, digest, now, now + CODE_LIFETIME, now - CODE_COOLDOWN,
        )
    if not should_send:
        return

    try:
        email_service.send_login_email(email, code)
    except (RuntimeError, httpx.HTTPError) as error:
        with session_scope() as db:
            user_repository.delete_login_code_if_matches(db, email, digest)
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
    token: str | None = None
    result: UserDTO | None = None

    with session_scope() as db:
        pending = user_repository.get_login_code_for_update(db, email)
        if pending is None or pending.expires_at <= now or pending.failed_attempts >= MAX_CODE_ATTEMPTS:
            pass
        elif not hmac.compare_digest(code_digest(body.code, pending.code_salt), pending.code_hash):
            pending.failed_attempts += 1
        else:
            db.delete(pending)
            user = user_repository.get_user_by_email_for_update(db, email)
            if user is None:
                user = user_repository.create_user_if_missing(
                    db, email, body.locale, body.time_zone, body.country,
                )
            if user.is_active and not user.is_deleted:
                user.email_verified = True
                user.last_login_at = now
                user_repository.record_login(db, user.id, ip_address, user_agent)
                token = new_session_token()
                user_repository.create_web_session(
                    db, token_digest(token), user.id, now + SESSION_LIFETIME,
                )
                result = to_user_dto(user)

    if result is None or token is None:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "验证码错误或已过期，或账号不可用")
    return result, token


def current_user(token: str | None) -> UserDTO:
    if not token:
        raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
    with session_scope() as db:
        user = user_repository.get_user_for_session(db, token_digest(token))
        if user is None:
            raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
        return to_user_dto(user)


def logout_user(token: str | None) -> None:
    if token:
        with session_scope() as db:
            user_repository.revoke_web_session(db, token_digest(token))
