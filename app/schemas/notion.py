"""User-triggered Notion page snapshot import contracts."""

from pydantic import BaseModel, Field

from app.schemas.file import FileUploadItemDTO


class NotionPageImportRequest(BaseModel):
    projectId: int = Field(gt=0)
    pageIdOrUrl: str = Field(min_length=1, max_length=500)


class NotionPageImportDTO(BaseModel):
    pageId: str
    pageUrl: str
    title: str
    snapshotLastEditedAt: str | None = None
    file: FileUploadItemDTO
