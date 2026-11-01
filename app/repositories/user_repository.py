"""PostgreSQL operations for users and login records."""

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.user import User


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


def get_active_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(
        User.id == user_id,
        User.is_active.is_(True),
        User.is_deleted.is_(False),
    ))
