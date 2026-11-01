"""Document contracts consumed by the Web Markdown editor."""

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.schemas.document import DocumentCreateRequest, DocumentDraftUpdateRequest
from app.services import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/list")
def list_documents(
    project_id: int = Query(alias="projectId", gt=0),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    rows = document_service.list_documents(user_id, project_id, offset, limit)
    return ok([item.model_dump(mode="json") for item in rows])


@router.post("/create")
def create_document(body: DocumentCreateRequest, user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(document_service.create_document(user_id, body).model_dump(mode="json"))


@router.get("/{document_id}")
def get_document(
    document_id: int = Path(gt=0), include_versions: bool = Query(default=False, alias="includeVersions"),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(document_service.get_document(user_id, document_id, include_versions).model_dump(mode="json"))


@router.put("/{document_id}/draft")
def update_draft(
    body: DocumentDraftUpdateRequest, document_id: int = Path(gt=0),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(document_service.update_draft(user_id, document_id, body).model_dump(mode="json"))
