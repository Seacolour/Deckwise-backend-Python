"""Owned Markdown documents and optimistic-lock draft editing."""

from datetime import datetime, timezone

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.models.document import Document
from app.repositories import document_repository
from app.schemas.document import (
    DocumentCreateRequest, DocumentDraftUpdateRequest, DocumentDTO, DocumentVersionDTO,
)
from app.services.project_service import require_owned_project


def _dto(document: Document, versions: list[DocumentVersionDTO] | None = None) -> DocumentDTO:
    return DocumentDTO(
        id=str(document.id), projectId=str(document.project_id), title=document.title,
        documentType=document.document_type.upper(),
        currentFileId=str(document.current_file_id) if document.current_file_id is not None else None,
        draftContent=document.draft_content,
        draftUpdatedAt=document.draft_updated_at.isoformat() if document.draft_updated_at else None,
        version=document.version, createdAt=document.created_at.isoformat(),
        updatedAt=document.updated_at.isoformat(), versions=versions,
    )


def _owned_document(db, user_id: int, document_id: int) -> Document:
    document = document_repository.get_owned_document(db, user_id, document_id)
    if document is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "文档不存在")
    return document


def create_document(user_id: int, body: DocumentCreateRequest) -> DocumentDTO:
    title = body.title.strip()
    if not title:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "文档标题不能为空")
    with session_scope() as db:
        require_owned_project(db, user_id, body.projectId)
        document = document_repository.create_document(
            db, body.projectId, user_id, title, body.draftContent, datetime.now(timezone.utc),
        )
        return _dto(document)


def list_documents(user_id: int, project_id: int, offset: int, limit: int) -> list[DocumentDTO]:
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)
        return [_dto(item) for item in document_repository.list_documents(db, project_id, offset, limit)]


def get_document(user_id: int, document_id: int, include_versions: bool) -> DocumentDTO:
    with session_scope() as db:
        document = _owned_document(db, user_id, document_id)
        versions = None
        if include_versions:
            versions = [DocumentVersionDTO(
                id=str(row["id"]), documentId=str(row["document_id"]),
                versionNo=row["version_no"], fileId=str(row["file_id"]),
                message=row["message"], createdBy=row["created_by"],
                createdAt=row["created_at"].isoformat(),
            ) for row in document_repository.list_versions(db, document_id)]
        return _dto(document, versions)


def update_draft(user_id: int, document_id: int, body: DocumentDraftUpdateRequest) -> DocumentDTO:
    with session_scope() as db:
        _owned_document(db, user_id, document_id)
        changed = document_repository.update_draft_if_version(
            db, document_id, body.version, body.draftContent, user_id, datetime.now(timezone.utc),
        )
        if not changed:
            raise BusinessError(409, ErrorCode.REVISION_CONFLICT, "文档版本已变化，请刷新后重试")
        db.expire_all()
        return _dto(_owned_document(db, user_id, document_id))
