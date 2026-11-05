"""Persistent user instructions shown in the existing personalization UI."""

from sqlalchemy import text

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.repositories import user_rule_repository
from app.schemas.personalization import UserRuleDTO

RULE_LIMIT = 50


def _dto(row: dict) -> UserRuleDTO:
    return UserRuleDTO(
        id=str(row["id"]), content=row["content"], enabled=bool(row["enabled"]),
        source=row["source"] or "user",
        createdAt=row["created_at"], updatedAt=row["updated_at"],
    )


def _content(value: str) -> str:
    content = value.strip()
    if not content or len(content) > 2000:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "规则内容无效")
    return content


def list_rules(user_id: int) -> list[UserRuleDTO]:
    with session_scope() as db:
        return [_dto(row) for row in user_rule_repository.list_by_user(db, user_id)]


def enabled_rules_context(user_id: int) -> str:
    rules = [row.content for row in list_rules(user_id) if row.enabled]
    return "\n".join(f"- {content[:500]}" for content in rules[:10])[:2_500]


def create_rule(user_id: int, value: str) -> UserRuleDTO:
    content = _content(value)
    with session_scope() as db:
        db.execute(text("SELECT id FROM backend_data.users WHERE id = :user_id FOR UPDATE"),
                   {"user_id": user_id})
        if user_rule_repository.count_by_user(db, user_id) >= RULE_LIMIT:
            raise BusinessError(400, ErrorCode.PARAMS_ERROR, "规则数量已达上限（50 条）")
        return _dto(user_rule_repository.insert(db, user_id, content))


def update_rule(user_id: int, rule_id: int, value: str) -> bool:
    with session_scope() as db:
        if not user_rule_repository.update(db, user_id, rule_id, _content(value)):
            raise BusinessError(404, ErrorCode.NOT_FOUND, "规则不存在")
    return True


def toggle_rule(user_id: int, rule_id: int, enabled: bool) -> bool:
    with session_scope() as db:
        if not user_rule_repository.set_enabled(db, user_id, rule_id, enabled):
            raise BusinessError(404, ErrorCode.NOT_FOUND, "规则不存在")
    return True


def delete_rule(user_id: int, rule_id: int) -> bool:
    with session_scope() as db:
        if not user_rule_repository.soft_delete(db, user_id, rule_id):
            raise BusinessError(404, ErrorCode.NOT_FOUND, "规则不存在")
    return True
