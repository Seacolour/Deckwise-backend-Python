"""User/Agent memory writes share one ownership and validation boundary."""

from sqlalchemy import text

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.repositories import user_memory_repository
from app.schemas.personalization import UserMemoryDTO

USER_LIMIT = 200
AGENT_LIMIT = 50
PROFILE_MEMORY_TITLE = "Deckwise personalization profile"


def _dto(row: dict) -> UserMemoryDTO:
    return UserMemoryDTO(
        id=str(row["id"]), title=row["title"], content=row["content"],
        source=row["source"] or "ai",
        createdAt=row["created_at"], updatedAt=row["updated_at"],
    )


def _fields(title: str, content: str) -> tuple[str, str]:
    title, content = title.strip(), content.strip()
    if not title or len(title) > 200 or not content or len(content) > 5000:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "记忆标题或内容无效")
    return title, content


def list_memories(user_id: int) -> list[UserMemoryDTO]:
    with session_scope() as db:
        return [_dto(row) for row in user_memory_repository.list_by_user(db, user_id)]


def create_memory(user_id: int, title: str, content: str, *, source: str = "user") -> UserMemoryDTO:
    title, content = _fields(title, content)
    if source not in {"user", "ai"}:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "记忆来源无效")
    with session_scope() as db:
        db.execute(text("SELECT id FROM backend_data.users WHERE id = :user_id FOR UPDATE"),
                   {"user_id": user_id})
        limit = AGENT_LIMIT if source == "ai" else USER_LIMIT
        if user_memory_repository.count_by_user(db, user_id) >= limit:
            raise BusinessError(400, ErrorCode.PARAMS_ERROR, f"记忆数量已达上限（{limit} 条）")
        return _dto(user_memory_repository.insert(db, user_id, title, content, source))


def update_memory(user_id: int, memory_id: int, title: str, content: str) -> UserMemoryDTO:
    title, content = _fields(title, content)
    with session_scope() as db:
        row = user_memory_repository.update(db, user_id, memory_id, title, content)
        if row is None:
            raise BusinessError(404, ErrorCode.NOT_FOUND, "记忆不存在")
        return _dto(row)


def delete_memory(user_id: int, memory_id: int) -> bool:
    with session_scope() as db:
        if not user_memory_repository.soft_delete(db, user_id, memory_id):
            raise BusinessError(404, ErrorCode.NOT_FOUND, "记忆不存在")
    return True
