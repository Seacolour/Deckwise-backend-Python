"""Markdown draft persistence, scoped reads, and atomic version updates."""

from datetime import datetime

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.project import Project


def create_document(
    db: Session, project_id: int, user_id: int, title: str,
    draft_content: str | None, now: datetime,
) -> Document:
    document = Document(
        project_id=project_id, title=title, document_type="markdown",
        draft_content=draft_content, draft_updated_at=now if draft_content is not None else None,
        version=1, created_by=user_id, updated_by=user_id,
        created_at=now, updated_at=now, is_deleted=False,
    )
    db.add(document)
    db.flush()
    return document


def list_documents(db: Session, project_id: int, offset: int, limit: int) -> list[Document]:
    return list(db.scalars(select(Document).where(
        Document.project_id == project_id, Document.is_deleted.is_(False),
    ).order_by(Document.updated_at.desc(), Document.id.desc()).offset(offset).limit(limit)).all())


def get_owned_document(db: Session, user_id: int, document_id: int) -> Document | None:
    return db.scalar(select(Document).join(Project, Project.id == Document.project_id).where(
        Document.id == document_id, Document.is_deleted.is_(False),
        Project.owner_id == user_id, Project.is_deleted.is_(False),
    ))


def update_draft_if_version(
    db: Session, document_id: int, version: int, content: str, user_id: int, now: datetime,
    expected_project_id: int | None = None,
) -> bool:
    filters = [
        Document.id == document_id,
        Document.version == version,
        Document.is_deleted.is_(False),
        Document.project_id.in_(select(Project.id).where(
            Project.owner_id == user_id, Project.is_deleted.is_(False),
        )),
    ]
    if expected_project_id is not None:
        filters.append(Document.project_id == expected_project_id)
    updated_id = db.scalar(update(Document).where(*filters).values(
        draft_content=content,
        draft_updated_at=now,
        updated_at=now,
        updated_by=user_id,
        version=Document.version + 1,
    ).returning(Document.id))
    return updated_id is not None


def list_versions(db: Session, document_id: int) -> list[dict[str, object]]:
    rows = db.execute(text("""
        SELECT id, document_id, version_no, file_id, message, created_by, created_at
        FROM backend_data.document_versions
        WHERE document_id = :document_id AND is_deleted = false
        ORDER BY version_no DESC
        LIMIT 50
    """), {"document_id": document_id}).mappings().all()
    return [dict(row) for row in rows]
