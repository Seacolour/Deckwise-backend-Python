"""One check-in per user per day in the user's bound time zone."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.models.checkin import UserCheckinStatus
from app.models.user import User
from app.repositories import checkin_repository
from app.schemas.checkin import CheckinRequest, CheckinResultDTO, CheckinStatusDTO


def _valid_zone(name: str | None) -> ZoneInfo | None:
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def _status_dto(status: UserCheckinStatus | None) -> CheckinStatusDTO:
    return CheckinStatusDTO(
        streakCount=status.streak_count if status else 0,
        longestStreak=status.longest_streak if status else 0,
        lastCheckinDate=status.last_checkin_date.isoformat() if status and status.last_checkin_date else None,
    )


def get_status(user_id: int) -> CheckinStatusDTO:
    with session_scope() as db:
        return _status_dto(checkin_repository.get_status(db, user_id))


def _bind_preferences(user: User, body: CheckinRequest | None) -> ZoneInfo:
    stored_zone = _valid_zone(user.preferred_time_zone)
    reported_zone = _valid_zone(body.timeZone) if body else None
    if not user.preferred_time_zone and reported_zone is not None:
        user.preferred_time_zone = body.timeZone
    if body and not user.preferred_locale and body.locale and body.locale.strip():
        user.preferred_locale = body.locale.strip()
    if body and not user.last_known_country and body.country:
        country = body.country.strip().upper()
        if len(country) == 2 and country.isalpha() and country.isascii():
            user.last_known_country = country
    return stored_zone or reported_zone or ZoneInfo("UTC")


def checkin(
    user_id: int, body: CheckinRequest | None, platform: str | None,
    app_version: str | None, ip_address: str | None, user_agent: str | None,
) -> CheckinResultDTO:
    with session_scope() as db:
        user = checkin_repository.lock_active_user(db, user_id)
        if user is None:
            raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
        zone = _bind_preferences(user, body)
        now = datetime.now(timezone.utc)
        day = now.astimezone(zone).date()
        status = checkin_repository.get_status(db, user_id)
        previous = _status_dto(status)

        if checkin_repository.has_checkin(db, user_id, day):
            return CheckinResultDTO(
                checkedIn=True, rewardPoints=0, streakAfter=previous.streakCount,
                longestStreak=previous.longestStreak, date=day.isoformat(),
            )

        streak = (previous.streakCount + 1) if status and status.last_checkin_date == day - timedelta(days=1) else 1
        longest = max(previous.longestStreak, streak)
        reward = 1000 if streak >= 7 else 500
        inserted = checkin_repository.insert_checkin(
            db, user_id, day, reward, streak,
            platform[:32] if platform else None,
            app_version[:32] if app_version else None,
            body.deviceType if body else None,
            body.deviceToken if body else None,
            ip_address[:64] if ip_address else None,
            user_agent[:512] if user_agent else None,
            now,
        )
        if not inserted:
            return CheckinResultDTO(
                checkedIn=True, rewardPoints=0, streakAfter=previous.streakCount,
                longestStreak=previous.longestStreak, date=day.isoformat(),
            )
        checkin_repository.upsert_status(db, user_id, day, streak, longest, now)
        return CheckinResultDTO(
            checkedIn=True, rewardPoints=reward, streakAfter=streak,
            longestStreak=longest, date=day.isoformat(),
        )
