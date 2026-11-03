"""Owned conversation sessions and durable Web message history."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.models.session import ConversationSession, SessionMessage
from app.repositories import session_repository
from app.schemas.agent import SessionCreateRequest, SessionMessageDTO
from app.schemas.project import SessionDTO
from app.services.project_service import require_owned_project, session_to_dto


def require_owned_session(db: Session, user_id: int, session_id: int) -> ConversationSession:
    session = session_repository.get_owned_session(db, user_id, session_id)
    if session is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "会话不存在")
    return session


def create_session(user_id: int, project_id: int, body: SessionCreateRequest) -> SessionDTO:
    title = (body.title or "新对话").strip() or "新对话"
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        project = require_owned_project(db, user_id, project_id)
        session = session_repository.create_session(db, user_id, project_id, title, now)
        project.last_active_at = now
        return session_to_dto(session)


def _message_dto(row: SessionMessage) -> SessionMessageDTO:
    return SessionMessageDTO(
        id=str(row.id), seq=row.seq, role=row.role, type=row.type,
        content=row.content, rawContent=row.raw_content, status=row.status,
    )


def list_messages(user_id: int, session_id: int, after_seq: int, limit: int) -> list[SessionMessageDTO]:
    with session_scope() as db:
        require_owned_session(db, user_id, session_id)
        rows = session_repository.list_messages_after(db, session_id, after_seq, limit)
        return [_message_dto(row) for row in rows]


def prepare_turn(
    user_id: int, session_id: int, text: str, *, include_history: bool = True,
) -> tuple[int, list[tuple[str, str]]]:
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        session = require_owned_session(db, user_id, session_id)
        history = ([(row.role, row.content or "") for row in session_repository.recent_chat_messages(db, session_id)]
                   if include_history else [])
        session_repository.append_messages(db, session_id, [("user", "text", text, "final")], now)
        session.last_user_message = text[:500]
        return session.project_id, history


def persist_turn_events(
    user_id: int, session_id: int, events: list[tuple[str, str, str]], status: str,
) -> None:
    entries = [(role, kind, content, status if role == "assistant" else "final")
               for role, kind, content in events if content]
    if not entries:
        return
    with session_scope() as db:
        require_owned_session(db, user_id, session_id)
        session_repository.append_messages(db, session_id, entries, datetime.now(timezone.utc))
