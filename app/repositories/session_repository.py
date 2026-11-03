"""Owned conversations and ordered message history in PostgreSQL."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.session import ConversationSession, SessionMessage


def create_session(db: Session, user_id: int, project_id: int, title: str, now: datetime) -> ConversationSession:
    session = ConversationSession(
        project_id=project_id, created_by=user_id, title=title,
        last_user_message=None, last_active_at=now, archived=False,
        created_at=now, updated_at=now, is_deleted=False,
    )
    db.add(session)
    db.flush()
    return session


def get_owned_session(db: Session, user_id: int, session_id: int) -> ConversationSession | None:
    return db.scalar(select(ConversationSession).join(Project, Project.id == ConversationSession.project_id).where(
        ConversationSession.id == session_id,
        ConversationSession.created_by == user_id,
        ConversationSession.is_deleted.is_(False),
        Project.owner_id == user_id,
        Project.is_deleted.is_(False),
    ))


def lock_session(db: Session, session_id: int) -> ConversationSession:
    return db.scalar(select(ConversationSession).where(ConversationSession.id == session_id).with_for_update())


def append_messages(
    db: Session, session_id: int, entries: list[tuple[str, str, str, str]], now: datetime,
) -> list[SessionMessage]:
    """Append (role, type, content, status) rows under the session row lock."""
    session = lock_session(db, session_id)
    next_seq = (db.scalar(select(func.max(SessionMessage.seq)).where(SessionMessage.session_id == session_id)) or 0) + 1
    rows: list[SessionMessage] = []
    for role, message_type, content, status in entries:
        row = SessionMessage(
            session_id=session_id, seq=next_seq, role=role, type=message_type,
            content=content, raw_content=content if message_type == "text" else None,
            status=status, created_at=now, updated_at=now, is_deleted=False,
        )
        db.add(row)
        rows.append(row)
        next_seq += 1
    session.last_active_at = now
    session.updated_at = now
    db.flush()
    return rows


def list_messages_after(db: Session, session_id: int, after_seq: int, limit: int) -> list[SessionMessage]:
    return list(db.scalars(select(SessionMessage).where(
        SessionMessage.session_id == session_id,
        SessionMessage.seq > after_seq,
        SessionMessage.is_deleted.is_(False),
    ).order_by(SessionMessage.seq.asc()).limit(limit)).all())


def recent_chat_messages(db: Session, session_id: int, limit: int = 30) -> list[SessionMessage]:
    rows = db.scalars(select(SessionMessage).where(
        SessionMessage.session_id == session_id,
        SessionMessage.is_deleted.is_(False),
        SessionMessage.role.in_(["user", "assistant"]),
        SessionMessage.type == "text",
        SessionMessage.status == "final",
    ).order_by(SessionMessage.seq.desc()).limit(limit)).all()
    return list(reversed(rows))
