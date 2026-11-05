"""User-owned custom rules used by the existing Web personalization page."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_by_user(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT id, content, enabled, source, created_at, updated_at
        FROM backend_data.user_rules
        WHERE user_id = :user_id AND is_deleted = false
        ORDER BY updated_at DESC, id DESC LIMIT 50
    """), {"user_id": user_id}).mappings().all()
    return [dict(row) for row in rows]


def count_by_user(db: Session, user_id: int) -> int:
    return int(db.scalar(text("""
        SELECT count(*) FROM backend_data.user_rules
        WHERE user_id = :user_id AND is_deleted = false
    """), {"user_id": user_id}) or 0)


def insert(db: Session, user_id: int, content: str) -> dict:
    row = db.execute(text("""
        INSERT INTO backend_data.user_rules (user_id, content, enabled, source, is_deleted)
        VALUES (:user_id, :content, true, 'user', false)
        RETURNING id, content, enabled, source, created_at, updated_at
    """), {"user_id": user_id, "content": content}).mappings().one()
    return dict(row)


def update(db: Session, user_id: int, rule_id: int, content: str) -> bool:
    return db.scalar(text("""
        UPDATE backend_data.user_rules SET content = :content
        WHERE id = :rule_id AND user_id = :user_id AND is_deleted = false
        RETURNING id
    """), {"user_id": user_id, "rule_id": rule_id, "content": content}) is not None


def set_enabled(db: Session, user_id: int, rule_id: int, enabled: bool) -> bool:
    return db.scalar(text("""
        UPDATE backend_data.user_rules SET enabled = :enabled
        WHERE id = :rule_id AND user_id = :user_id AND is_deleted = false
        RETURNING id
    """), {"user_id": user_id, "rule_id": rule_id, "enabled": enabled}) is not None


def soft_delete(db: Session, user_id: int, rule_id: int) -> bool:
    return db.scalar(text("""
        UPDATE backend_data.user_rules SET is_deleted = true
        WHERE id = :rule_id AND user_id = :user_id AND is_deleted = false
        RETURNING id
    """), {"user_id": user_id, "rule_id": rule_id}) is not None
