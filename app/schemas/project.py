"""Workspace project contracts used by the existing Web client."""

from pydantic import BaseModel, Field

from app.schemas.pagination import PageRequest


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    coverImage: str | None = Field(default=None, max_length=2048)
    tags: list[str] | None = Field(default=None, max_length=20)


class ProjectListQuery(PageRequest):
    archived: bool | None = None


class ProjectDTO(BaseModel):
    id: str
    ownerId: str
    name: str
    description: str | None
    coverImage: str | None
    tags: list[str] | None
    archived: bool
    lastActiveAt: str | None
    createdAt: str
    updatedAt: str


class SessionDTO(BaseModel):
    id: str
    projectId: str
    createdBy: int
    title: str
    lastUserMessage: str | None
    lastActiveAt: str | None
    archived: bool
    createdAt: str
    updatedAt: str


class ProjectFileDTO(BaseModel):
    id: str
    projectId: str
    cacheKey: str
    fileName: str
    addedAt: str
    documentId: str | None = None
    sourceId: str | None = None
    sizeBytes: int | None = None
    objectKey: str | None = None
