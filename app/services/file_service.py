"""Private project uploads and bounded parsed-content reads."""

import hashlib
import logging
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.core.r2_storage import (
    delete_private_object, new_object_key, presigned_read_url,
    private_settings, put_private_object,
)
from app.db.session import session_scope
from app.repositories import file_repository
from app.schemas.file import (
    FileContentPageDTO, FileFragmentDTO, FileUploadBatchDTO,
    FileUploadItemDTO, PrivateObjectAccessUrlDTO,
)
from app.services.file_parse_service import MAX_FILE_BYTES, ParsedFile, parse_file, safe_filename
from app.services.project_service import require_owned_project

logger = logging.getLogger("uvicorn.error")
MAX_BATCH_FILES = 20


def _upload_item(
    file_id: int, name: str, size: int, cache_key: str,
    parsed: ParsedFile, object_key: str,
) -> FileUploadItemDTO:
    return FileUploadItemDTO(
        sourceFileId=str(file_id), fileId=str(file_id), fileName=name,
        fileSize=size, sizeBytes=size, mimeType=parsed.mime_type,
        objectKey=object_key, cacheKey=cache_key,
        totalFragments=len(parsed.fragments),
    )


def upload_one(user_id: int, project_id: int, file: UploadFile) -> FileUploadItemDTO:
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)
    name = safe_filename(file.filename)
    data = file.file.read(MAX_FILE_BYTES + 1)
    parsed = parse_file(name, data)
    cache_key = hashlib.sha256(data).hexdigest()
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)
        existing = file_repository.find_existing_file(db, user_id, cache_key)
        if existing:
            file_repository.attach_file(db, project_id, existing["id"], user_id, name)
            if file_repository.count_fragments(db, existing["id"]) == 0:
                file_repository.insert_fragments(db, existing["id"], parsed.fragments, parsed.extension)
            return _upload_item(existing["id"], name, len(data), cache_key, parsed, existing["object_key"])

    settings = private_settings()
    object_key = new_object_key(settings, user_id, parsed.extension)
    try:
        etag = put_private_object(settings, object_key, data, parsed.mime_type)
    except (BotoCoreError, ClientError) as error:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "文件存储失败，请稍后重试") from error

    try:
        with session_scope() as db:
            require_owned_project(db, user_id, project_id)
            file_id = file_repository.insert_file(
                db, user_id, cache_key, name, settings.bucket, object_key,
                len(data), parsed.mime_type, parsed.extension, parsed.text_chars,
                len(parsed.fragments),
                "pypandoc" if parsed.extension == ".docx" else "pypdf" if parsed.extension == ".pdf" else "utf-8",
                etag,
            )
            file_repository.insert_fragments(db, file_id, parsed.fragments, parsed.extension)
            file_repository.attach_file(db, project_id, file_id, user_id, name)
        return _upload_item(file_id, name, len(data), cache_key, parsed, object_key)
    except Exception:
        try:
            delete_private_object(settings, object_key)
        except (BotoCoreError, ClientError):
            logger.warning("orphaned upload cleanup failed key=%s", object_key)
        raise


def upload_batch(
    user_id: int, project_id: int, files: list[UploadFile], upload_source: str | None,
) -> FileUploadBatchDTO:
    if upload_source not in (None, "user_upload", "reusable"):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "uploadSource 仅支持 user_upload/reusable")
    if not files or len(files) > MAX_BATCH_FILES:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "一次可上传 1–20 个文件")
    uploaded = [upload_one(user_id, project_id, file) for file in files]
    return FileUploadBatchDTO(
        batchId=str(uuid4()), projectId=str(project_id),
        totalCount=len(uploaded), files=uploaded,
    )


def require_project_file(user_id: int, project_id: int, cache_key: str) -> dict:
    with session_scope() as db:
        row = file_repository.find_project_file(db, user_id, project_id, cache_key=cache_key)
    if row is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "文件不存在")
    return row


def read_file_fragments(
    user_id: int, project_id: int, cache_key: str, start_index: int, limit: int,
) -> FileContentPageDTO:
    if start_index < 0 or not 1 <= limit <= 5:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "分片范围无效")
    with session_scope() as db:
        row = file_repository.find_project_file(db, user_id, project_id, cache_key=cache_key)
        if row is None:
            raise BusinessError(404, ErrorCode.NOT_FOUND, "文件不存在")
        total = file_repository.count_fragments(db, row["id"])
        fragments = file_repository.list_fragments(db, row["id"], start_index, limit)
    if total == 0:
        raise BusinessError(422, ErrorCode.PARAMS_ERROR, "文件尚无可读取的解析文本")
    next_index = fragments[-1]["fragment_index"] + 1 if fragments else start_index
    return FileContentPageDTO(
        fileId=str(row["id"]), cacheKey=cache_key,
        fileName=row["display_name"] or row["original_name"] or f"文件 {row['id']}",
        startIndex=start_index, totalFragments=total,
        fragments=[FileFragmentDTO(index=item["fragment_index"], content=item["fragment_content"])
                   for item in fragments],
        hasMore=next_index < total,
    )


def file_access_url(user_id: int, project_id: int, file_id: int) -> PrivateObjectAccessUrlDTO:
    with session_scope() as db:
        row = file_repository.find_project_file(db, user_id, project_id, file_id=file_id)
    if row is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "文件不存在")
    settings = private_settings()
    if row["bucket"] != settings.bucket:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "文件存储配置不匹配")
    return PrivateObjectAccessUrlDTO(accessUrl=presigned_read_url(settings, row["object_key"]))
