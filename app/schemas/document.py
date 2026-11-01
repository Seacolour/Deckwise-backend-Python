"""The current Web's Markdown document response shape."""

from typing import Literal

from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    projectId: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    draftContent: str | None = None
    documentType: Literal["MARKDOWN"] = "MARKDOWN"


class DocumentDraftUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    draftContent: str


class DocumentVersionDTO(BaseModel):
    id: str
    documentId: str
    versionNo: int
    fileId: str
    message: str | None
    createdBy: int | None
    createdAt: str


class DocumentDTO(BaseModel):
    id: str
    projectId: str
    title: str
    documentType: str
    currentFileId: str | None = None
    draftContent: str | None = None
    draftUpdatedAt: str | None = None
    version: int
    createdAt: str
    updatedAt: str
    versions: list[DocumentVersionDTO] | None = None
