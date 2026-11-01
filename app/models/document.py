"""The Markdown document row; its API and repository follow in the next slice."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": "backend_data"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("backend_data.projects.id"))
    title: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    draft_content: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(Boolean)
