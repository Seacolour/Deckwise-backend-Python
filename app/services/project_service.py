"""Workspace project ownership, lists, and Web DTOs."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.models.project import Project
from app.models.session import ConversationSession
from app.repositories import project_repository
from app.schemas.pagination import PageRequest, PageResponse
from app.schemas.project import (
    ProjectCreateRequest, ProjectDTO, ProjectFileDTO, ProjectListQuery, SessionDTO,
)


def require_owned_project(db: Session, user_id: int, project_id: int) -> Project:
    project = project_repository.get_owned_project(db, user_id, project_id)
    if project is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "项目不存在")
    return project


def _project_dto(project: Project) -> ProjectDTO:
    return ProjectDTO(
        id=str(project.id), ownerId=str(project.owner_id), name=project.name,
        description=project.description, coverImage=project.cover_image, tags=project.tags,
        archived=project.archived,
        lastActiveAt=project.last_active_at.isoformat() if project.last_active_at else None,
        createdAt=project.created_at.isoformat(), updatedAt=project.updated_at.isoformat(),
    )


def session_to_dto(session: ConversationSession) -> SessionDTO:
    return SessionDTO(
        id=str(session.id), projectId=str(session.project_id), createdBy=session.created_by,
        title=session.title, lastUserMessage=session.last_user_message,
        lastActiveAt=session.last_active_at.isoformat() if session.last_active_at else None,
        archived=session.archived, createdAt=session.created_at.isoformat(),
        updatedAt=session.updated_at.isoformat(),
    )


def create_project(user_id: int, body: ProjectCreateRequest) -> ProjectDTO:
    if not body.name.strip():
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "项目名称不能为空")
    with session_scope() as db:
        project = project_repository.create_project(db, user_id, body, datetime.now(timezone.utc))
        return _project_dto(project)


def list_projects(user_id: int, query: ProjectListQuery) -> PageResponse[ProjectDTO]:
    if not project_repository.valid_project_sort(query.sort_field):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "不支持的排序字段")
    with session_scope() as db:
        rows, total = project_repository.list_projects(db, user_id, query)
        return PageResponse[ProjectDTO].of(
            query.current, query.page_size, total, [_project_dto(row) for row in rows],
        )


def list_sessions(
    user_id: int, project_id: int, query: PageRequest, archived: bool | None,
) -> PageResponse[SessionDTO]:
    if not project_repository.valid_session_sort(query.sort_field):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "不支持的排序字段")
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)
        rows, total = project_repository.list_sessions(db, project_id, query, archived)
        return PageResponse[SessionDTO].of(
            query.current, query.page_size, total, [session_to_dto(row) for row in rows],
        )


def list_project_files(user_id: int, project_id: int) -> list[ProjectFileDTO]:
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)
        rows = project_repository.list_project_files(db, project_id)
        return [ProjectFileDTO(
            id=str(row["id"]), projectId=str(row["project_id"]),
            cacheKey=str(row["cache_key"]), fileName=str(row["file_name"]),
            addedAt=row["added_at"].isoformat(),
            documentId=str(row["document_id"]) if row["document_id"] is not None else None,
            sourceId=row["source_id"], sizeBytes=row["size_bytes"], objectKey=row["object_key"],
        ) for row in rows]
