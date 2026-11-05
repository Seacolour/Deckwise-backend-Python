"""Canonical editable user memories in the reused PostgreSQL schema."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_by_user(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT id, title, content, source, created_at, updated_at
        FROM backend_data.user_memories
        WHERE user_id = :user_id AND is_deleted = false
        ORDER BY updated_at DESC, id DESC
        LIMIT 200
    """), {"user_id": user_id}).mappings().all()
    return [dict(row) for row in rows]


def get_owned(db: Session, user_id: int, memory_id: int) -> dict | None:
    row = db.execute(text("""
        SELECT id, title, content, source, created_at, updated_at
        FROM backend_data.user_memories
        WHERE id = :memory_id AND user_id = :user_id AND is_deleted = false
    """), {"user_id": user_id, "memory_id": memory_id}).mappings().one_or_none()
    return dict(row) if row else None


def count_by_user(db: Session, user_id: int) -> int:
    return int(db.scalar(text("""
        SELECT count(*) FROM backend_data.user_memories
        WHERE user_id = :user_id AND is_deleted = false
    """), {"user_id": user_id}) or 0)


def insert(db: Session, user_id: int, title: str, content: str, source: str) -> dict:
    row = db.execute(text("""
        INSERT INTO backend_data.user_memories (user_id, title, content, source, is_deleted)
        VALUES (:user_id, :title, :content, :source, false)
        RETURNING id, title, content, source, created_at, updated_at
    """), {"user_id": user_id, "title": title, "content": content,
           "source": source}).mappings().one()
    return dict(row)


def update(db: Session, user_id: int, memory_id: int, title: str, content: str) -> dict | None:
    row = db.execute(text("""
        UPDATE backend_data.user_memories SET title = :title, content = :content
        WHERE id = :memory_id AND user_id = :user_id AND is_deleted = false
        RETURNING id, title, content, source, created_at, updated_at
    """), {"user_id": user_id, "memory_id": memory_id,
           "title": title, "content": content}).mappings().one_or_none()
    return dict(row) if row else None


def soft_delete(db: Session, user_id: int, memory_id: int) -> bool:
    return db.scalar(text("""
        UPDATE backend_data.user_memories SET is_deleted = true
        WHERE id = :memory_id AND user_id = :user_id AND is_deleted = false
        RETURNING id
    """), {"user_id": user_id, "memory_id": memory_id}) is not None
