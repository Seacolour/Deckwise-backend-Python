"""Private project file uploads, parsed text, and preview URLs."""

from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile

from app.api.dependencies import current_user_id
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.core.responses import ok
from app.services import file_service, model_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload/batch")
def upload_batch(
    files: list[UploadFile] = File(...),
    project_id: int = Query(alias="projectId", gt=0),
    upload_source: str | None = Query(default=None, alias="uploadSource"),
    model_id: str | None = Query(default=None, alias="model"),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    if any(FilePath(item.filename or "").suffix.lower() in image_extensions
           or (item.content_type or "").lower().startswith("image/") for item in files):
        if not model_id or not model_service.supports_images(user_id, model_id):
            raise BusinessError(400, ErrorCode.PARAMS_ERROR,
                                "当前模型不支持图片上传，请切换到 OpenRouter GPT 视觉模型")
    result = file_service.upload_batch(user_id, project_id, files, upload_source)
    return ok(result.model_dump(mode="json"))


@router.get("/{file_id}/access-url")
def access_url(
    file_id: int = Path(gt=0), project_id: int = Query(alias="projectId", gt=0),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(file_service.file_access_url(user_id, project_id, file_id).model_dump(mode="json"))
