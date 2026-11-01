"""Project ownership mapping used by future workspace APIs."""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"schema": "backend_data"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("backend_data.users.id"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean)
    is_deleted: Mapped[bool] = mapped_column(Boolean)
