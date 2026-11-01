"""Daily check-in status and audit rows."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserCheckinStatus(Base):
    __tablename__ = "user_checkin_status"
    __table_args__ = {"schema": "backend_data"}

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("backend_data.users.id"), primary_key=True)
    streak_count: Mapped[int] = mapped_column(Integer)
    longest_streak: Mapped[int] = mapped_column(Integer)
    last_checkin_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(Boolean)


class UserCheckinLog(Base):
    __tablename__ = "user_checkin_log"
    __table_args__ = {"schema": "backend_data"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("backend_data.users.id"))
    checkin_date: Mapped[date] = mapped_column(Date)
    platform: Mapped[str | None] = mapped_column(Text)
    app_version: Mapped[str | None] = mapped_column(Text)
    device_type: Mapped[str | None] = mapped_column(Text)
    device_token: Mapped[str | None] = mapped_column(Text)
    reward_points: Mapped[int] = mapped_column(Integer)
    streak_after: Mapped[int] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(Boolean)
