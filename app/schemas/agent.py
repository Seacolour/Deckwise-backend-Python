"""Conversation API and SSE request contracts used by the Web workbench."""

from typing import Literal

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ActiveDocumentContext(BaseModel):
    documentId: int = Field(gt=0)
    type: str | None = None
    fileName: str | None = None


class UserMessageClientContext(BaseModel):
    activeDocument: ActiveDocumentContext | None = None
    referencedDocumentIds: list[int] = Field(default_factory=list, max_length=5)


class UserMessageSendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    mode: Literal["ASK", "AGENT"] = "ASK"
    model: str = Field(min_length=1, max_length=120)
    clientContext: UserMessageClientContext | None = None
    fileCacheKeys: list[str] = Field(default_factory=list)
    imageCacheKeys: list[str] = Field(default_factory=list)


class SessionMessageDTO(BaseModel):
    id: str
    seq: int
    role: str
    type: str
    content: str | None
    rawContent: str | None
    status: str
    agentMessageGroupId: str | None = None
