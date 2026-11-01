"""PostgreSQL user mapping for the Python login feature."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "backend_data"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    email_verified: Mapped[bool | None] = mapped_column(Boolean)
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    sign_up_provider: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    preferred_locale: Mapped[str | None] = mapped_column(Text)
    preferred_time_zone: Mapped[str | None] = mapped_column(Text)
    last_known_country: Mapped[str | None] = mapped_column(String(2))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    is_deleted: Mapped[bool | None] = mapped_column(Boolean)
