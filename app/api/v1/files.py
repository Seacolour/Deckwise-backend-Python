"""Private project file uploads, parsed text, and preview URLs."""

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.services import file_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload/batch")
def upload_batch(
    files: list[UploadFile] = File(...),
    project_id: int = Query(alias="projectId", gt=0),
    upload_source: str | None = Query(default=None, alias="uploadSource"),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    result = file_service.upload_batch(user_id, project_id, files, upload_source)
    return ok(result.model_dump(mode="json"))


@router.get("/{file_id}/access-url")
def access_url(
    file_id: int = Path(gt=0), project_id: int = Query(alias="projectId", gt=0),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(file_service.file_access_url(user_id, project_id, file_id).model_dump(mode="json"))
