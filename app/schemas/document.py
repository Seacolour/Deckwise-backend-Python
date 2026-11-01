"""The current Web's Markdown document response shape."""

from pydantic import BaseModel


class DocumentDTO(BaseModel):
    id: str
    projectId: str
    title: str
    documentType: str
    draftContent: str | None = None
    version: int
