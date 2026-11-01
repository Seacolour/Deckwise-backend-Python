"""Persistence operations for email codes, users, and Web sessions."""

from datetime import datetime, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.user import EmailLoginCode, User, WebAuthSession


def upsert_login_code(
    db: Session, email: str, salt: bytes, digest: bytes,
    sent_at: datetime, expires_at: datetime, cooldown_before: datetime,
) -> bool:
    statement = insert(EmailLoginCode).values(
        email=email, code_salt=salt, code_hash=digest,
        sent_at=sent_at, expires_at=expires_at, failed_attempts=0,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[EmailLoginCode.email],
        set_={
            "code_salt": statement.excluded.code_salt,
            "code_hash": statement.excluded.code_hash,
            "sent_at": statement.excluded.sent_at,
            "expires_at": statement.excluded.expires_at,
            "failed_attempts": 0,
        },
        where=EmailLoginCode.sent_at <= cooldown_before,
    ).returning(EmailLoginCode.email)
    return db.scalar(statement) is not None


def delete_login_code_if_matches(db: Session, email: str, digest: bytes) -> None:
    db.execute(delete(EmailLoginCode).where(
        EmailLoginCode.email == email,
        EmailLoginCode.code_hash == digest,
    ))


def get_login_code_for_update(db: Session, email: str) -> EmailLoginCode | None:
    return db.scalar(select(EmailLoginCode).where(EmailLoginCode.email == email).with_for_update())


def get_user_by_email_for_update(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email).with_for_update())


def create_user_if_missing(
    db: Session, email: str, locale: str | None,
    time_zone: str | None, country: str | None,
) -> User:
    db.execute(insert(User).values(
        email=email, email_verified=True, sign_up_provider="email",
        preferred_locale=locale, preferred_time_zone=time_zone,
        last_known_country=country.upper() if country else None,
    ).on_conflict_do_nothing(index_elements=[User.email]))
    user = get_user_by_email_for_update(db, email)
    if user is None:
        raise RuntimeError("User insert did not create a row")
    return user


def record_login(db: Session, user_id: int, ip_address: str | None, user_agent: str) -> None:
    db.execute(text(
        "INSERT INTO backend_data.user_login_log "
        "(user_id, ip_address, user_agent, provider, success) "
        "VALUES (:user_id, :ip, :user_agent, 'email', true)"
    ), {"user_id": user_id, "ip": ip_address, "user_agent": user_agent[:512]})


def create_web_session(db: Session, token_hash: bytes, user_id: int, expires_at: datetime) -> None:
    db.add(WebAuthSession(token_hash=token_hash, user_id=user_id, expires_at=expires_at))


def get_user_for_session(db: Session, token_hash: bytes) -> User | None:
    return db.scalar(
        select(User)
        .join(WebAuthSession, WebAuthSession.user_id == User.id)
        .where(
            WebAuthSession.token_hash == token_hash,
            WebAuthSession.expires_at > datetime.now(timezone.utc),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
def revoke_web_session(db: Session, token_hash: bytes) -> None:
    db.execute(delete(WebAuthSession).where(WebAuthSession.token_hash == token_hash))
