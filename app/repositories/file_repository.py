"""Persist private upload metadata and parsed text fragments."""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

def find_existing_file(db: Session, user_id: int, cache_key: str,
                       source_type: str = "bytes") -> dict | None:
    row = db.execute(text("""
        SELECT id, original_name, mime_type, size_bytes, bucket, object_key
        FROM backend_data.object_storage_files
        WHERE owner_user_id = :user_id AND source_type = :source_type
          AND source_key = :cache_key AND storage_channel = 'private'
          AND status = 'available' AND is_deleted = false
        LIMIT 1
    """), {"user_id": user_id, "source_type": source_type,
           "cache_key": cache_key}).mappings().one_or_none()
    return dict(row) if row else None


def insert_file(
    db: Session, user_id: int, cache_key: str, name: str,
    bucket: str, object_key: str, size: int, mime_type: str,
    extension: str, text_chars: int, total_fragments: int, parser: str,
    etag: str | None,
    source_type: str = "bytes", source_id: str | None = None,
    source_url: str | None = None,
) -> int:
    metadata = json.dumps({
        "parser": parser,
        "text_chars": text_chars,
        "total_fragments": total_fragments,
        **({"source_url": source_url} if source_url else {}),
    })
    return db.scalar(text("""
        INSERT INTO backend_data.object_storage_files
            (owner_user_id, source_type, source_key, storage_type, bucket, object_key,
             mime_type, file_ext, size_bytes, original_name, etag, status,
             storage_channel, visibility, source_id, metadata)
        VALUES (:user_id, :source_type, :cache_key, 'r2', :bucket, :object_key,
                :mime_type, :file_ext, :size, :name, :etag, 'available',
                'private', 'private', :source_id, CAST(:metadata AS jsonb))
        RETURNING id
    """), {
        "user_id": user_id, "cache_key": cache_key, "bucket": bucket,
        "object_key": object_key, "mime_type": mime_type,
        "file_ext": extension.lstrip("."), "size": size,
        "name": name, "etag": etag, "metadata": metadata,
        "source_type": source_type, "source_id": source_id,
    })


def attach_file(db: Session, project_id: int, file_id: int, user_id: int, name: str) -> None:
    db.execute(text("""
        INSERT INTO backend_data.project_file_links
            (project_id, file_id, added_by, display_name, kind, is_deleted)
        VALUES (:project_id, :file_id, :user_id, :name, 'file', false)
        ON CONFLICT (project_id, file_id) DO UPDATE
        SET is_deleted = false, display_name = EXCLUDED.display_name
    """), {"project_id": project_id, "file_id": file_id, "user_id": user_id, "name": name})


def count_fragments(db: Session, file_id: int) -> int:
    return db.scalar(text("""
        SELECT count(*) FROM backend_data.file_text_fragments
        WHERE file_id = :file_id AND is_deleted = false
    """), {"file_id": file_id}) or 0


def insert_fragments(db: Session, file_id: int, fragments: list[str], extension: str) -> None:
    rows = [
        {"file_id": file_id, "index": index, "content": content,
         "kind": extension.lstrip("."), "total": len(fragments)}
        for index, content in enumerate(fragments)
    ]
    db.execute(text("""
        INSERT INTO backend_data.file_text_fragments
            (file_id, fragment_index, fragment_content, message_type, total_fragments, is_deleted)
        VALUES (:file_id, :index, :content, :kind, :total, false)
        ON CONFLICT (file_id, fragment_index) DO UPDATE
        SET fragment_content = EXCLUDED.fragment_content,
            message_type = EXCLUDED.message_type,
            total_fragments = EXCLUDED.total_fragments,
            is_deleted = false
    """), rows)


def find_project_file(
    db: Session, user_id: int, project_id: int,
    *, cache_key: str | None = None, file_id: int | None = None,
) -> dict | None:
    row = db.execute(text("""
        SELECT f.id, f.source_key AS cache_key, f.original_name, f.mime_type,
               f.size_bytes, f.bucket, f.object_key, l.display_name
        FROM backend_data.object_storage_files AS f
        JOIN backend_data.project_file_links AS l ON l.file_id = f.id
        JOIN backend_data.projects AS p ON p.id = l.project_id
        WHERE p.owner_id = :user_id AND p.id = :project_id AND p.is_deleted = false
          AND l.is_deleted = false AND f.is_deleted = false AND f.status = 'available'
          AND f.storage_channel = 'private'
          AND (CAST(:cache_key AS text) IS NULL OR f.source_key = :cache_key)
          AND (CAST(:file_id AS bigint) IS NULL OR f.id = :file_id)
        LIMIT 1
    """), {
        "user_id": user_id, "project_id": project_id,
        "cache_key": cache_key, "file_id": file_id,
    }).mappings().one_or_none()
    return dict(row) if row else None


def list_fragments(db: Session, file_id: int, start_index: int, limit: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT fragment_index, fragment_content, total_fragments
        FROM backend_data.file_text_fragments
        WHERE file_id = :file_id AND fragment_index >= :start_index
          AND is_deleted = false
        ORDER BY fragment_index ASC
        LIMIT :limit
    """), {"file_id": file_id, "start_index": start_index, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def list_project_fragments_for_index(
    db: Session, user_id: int, project_id: int, limit: int,
    cache_key: str | None = None,
) -> list[dict]:
    """Return only currently linked text fragments from an owned project."""
    rows = db.execute(text("""
        SELECT f.id AS file_id, f.source_key AS cache_key,
               COALESCE(l.display_name, f.original_name) AS file_name,
               t.fragment_index, t.fragment_content
        FROM backend_data.projects AS p
        JOIN backend_data.project_file_links AS l ON l.project_id = p.id
        JOIN backend_data.object_storage_files AS f ON f.id = l.file_id
        JOIN backend_data.file_text_fragments AS t ON t.file_id = f.id
        WHERE p.id = :project_id AND p.owner_id = :user_id AND p.is_deleted = false
          AND l.is_deleted = false AND f.is_deleted = false AND f.status = 'available'
          AND f.storage_channel = 'private' AND t.is_deleted = false
          AND (CAST(:cache_key AS text) IS NULL OR f.source_key = :cache_key)
        ORDER BY f.id, t.fragment_index
        LIMIT :limit
    """), {"user_id": user_id, "project_id": project_id,
           "cache_key": cache_key, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]
