"""PostgreSQL reads and writes for owned workspace projects."""

from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.session import ConversationSession
from app.schemas.pagination import PageRequest
from app.schemas.project import ProjectCreateRequest, ProjectListQuery

_PROJECT_SORT = {
    "updatedAt": Project.updated_at,
    "createdAt": Project.created_at,
    "lastActiveAt": Project.last_active_at,
    "name": Project.name,
}
_SESSION_SORT = {
    "lastActiveAt": ConversationSession.last_active_at,
    "createdAt": ConversationSession.created_at,
    "updatedAt": ConversationSession.updated_at,
    "title": ConversationSession.title,
}


def get_owned_project(db: Session, user_id: int, project_id: int) -> Project | None:
    return db.scalar(select(Project).where(
        Project.id == project_id,
        Project.owner_id == user_id,
        Project.is_deleted.is_(False),
    ))


def create_project(db: Session, user_id: int, body: ProjectCreateRequest, now: datetime) -> Project:
    project = Project(
        owner_id=user_id,
        name=body.name.strip(),
        description=body.description,
        cover_image=body.coverImage,
        tags=body.tags,
        archived=False,
        is_deleted=False,
        last_active_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    return project


def list_projects(db: Session, user_id: int, query: ProjectListQuery) -> tuple[list[Project], int]:
    filters = [Project.owner_id == user_id, Project.is_deleted.is_(False)]
    if query.archived is not None:
        filters.append(Project.archived.is_(query.archived))
    column = _PROJECT_SORT[query.sort_field or "updatedAt"]
    direction = query.sort_order if query.sort_field else "desc"
    order = column.asc() if direction == "asc" else column.desc()
    total = db.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    rows = db.scalars(select(Project).where(*filters).order_by(order, Project.id.desc())
                      .offset(query.offset).limit(query.page_size)).all()
    return list(rows), total


def valid_project_sort(field: str | None) -> bool:
    return field is None or field in _PROJECT_SORT


def valid_session_sort(field: str | None) -> bool:
    return field is None or field in _SESSION_SORT


def list_sessions(
    db: Session, project_id: int, query: PageRequest, archived: bool | None,
) -> tuple[list[ConversationSession], int]:
    filters = [ConversationSession.project_id == project_id, ConversationSession.is_deleted.is_(False)]
    if archived is not None:
        filters.append(ConversationSession.archived.is_(archived))
    column = _SESSION_SORT[query.sort_field or "lastActiveAt"]
    direction = query.sort_order if query.sort_field else "desc"
    order = column.asc() if direction == "asc" else column.desc()
    total = db.scalar(select(func.count()).select_from(ConversationSession).where(*filters)) or 0
    rows = db.scalars(select(ConversationSession).where(*filters)
                      .order_by(order, ConversationSession.id.desc())
                      .offset(query.offset).limit(query.page_size)).all()
    return list(rows), total


def list_project_files(db: Session, project_id: int) -> list[dict[str, object]]:
    rows = db.execute(text("""
        SELECT f.id, l.project_id, f.source_key AS cache_key,
               COALESCE(NULLIF(l.display_name, ''), NULLIF(f.original_name, ''), '文件 ' || f.id::text) AS file_name,
               l.created_at AS added_at, f.source_id, f.source_type, f.size_bytes, f.object_key,
               d.id AS document_id
        FROM backend_data.project_file_links AS l
        JOIN backend_data.object_storage_files AS f ON f.id = l.file_id
        LEFT JOIN LATERAL (
            SELECT id FROM backend_data.documents
            WHERE project_id = l.project_id AND current_file_id = f.id AND is_deleted = false
            ORDER BY updated_at DESC, id DESC LIMIT 1
        ) AS d ON true
        WHERE l.project_id = :project_id AND l.is_deleted = false
          AND f.is_deleted = false AND f.status = 'available'
        ORDER BY l.created_at DESC, l.id DESC
    """), {"project_id": project_id}).mappings().all()
    return [dict(row) for row in rows]
