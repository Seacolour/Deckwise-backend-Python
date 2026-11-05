"""Web-compatible user memory, rule, and profile contracts."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserMemoryCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)


class UserMemoryUpdateRequest(UserMemoryCreateRequest):
    pass


class UserMemoryDTO(BaseModel):
    id: str
    title: str
    content: str
    source: str
    createdAt: datetime
    updatedAt: datetime


class UserRuleRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class UserRuleDTO(BaseModel):
    id: str
    content: str
    enabled: bool
    source: str
    createdAt: datetime
    updatedAt: datetime


class UpdateCurrentUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
