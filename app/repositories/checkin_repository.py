"""Transactional PostgreSQL access for daily check-ins."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.checkin import UserCheckinLog, UserCheckinStatus
from app.models.user import User


def lock_active_user(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(
        User.id == user_id, User.is_active.is_(True), User.is_deleted.is_(False),
    ).with_for_update())


def get_status(db: Session, user_id: int) -> UserCheckinStatus | None:
    return db.scalar(select(UserCheckinStatus).where(
        UserCheckinStatus.user_id == user_id, UserCheckinStatus.is_deleted.is_(False),
    ))


def has_checkin(db: Session, user_id: int, day: date) -> bool:
    return db.scalar(select(UserCheckinLog.id).where(
        UserCheckinLog.user_id == user_id,
        UserCheckinLog.checkin_date == day,
        UserCheckinLog.is_deleted.is_(False),
    )) is not None


def insert_checkin(
    db: Session, user_id: int, day: date, reward: int, streak: int,
    platform: str | None, app_version: str | None,
    device_type: str | None, device_token: str | None,
    ip_address: str | None, user_agent: str | None, now: datetime,
) -> bool:
    statement = insert(UserCheckinLog).values(
        user_id=user_id, checkin_date=day, reward_points=reward, streak_after=streak,
        platform=platform, app_version=app_version, device_type=device_type,
        device_token=device_token, ip_address=ip_address, user_agent=user_agent,
        created_at=now, is_deleted=False,
    ).on_conflict_do_nothing(
        index_elements=[UserCheckinLog.user_id, UserCheckinLog.checkin_date],
    ).returning(UserCheckinLog.id)
    return db.scalar(statement) is not None


def upsert_status(
    db: Session, user_id: int, day: date, streak: int, longest: int, now: datetime,
) -> None:
    statement = insert(UserCheckinStatus).values(
        user_id=user_id, streak_count=streak, longest_streak=longest,
        last_checkin_date=day, created_at=now, updated_at=now, is_deleted=False,
    )
    db.execute(statement.on_conflict_do_update(
        index_elements=[UserCheckinStatus.user_id],
        set_={
            "streak_count": streak,
            "longest_streak": longest,
            "last_checkin_date": day,
            "updated_at": now,
            "is_deleted": False,
        },
    ))
