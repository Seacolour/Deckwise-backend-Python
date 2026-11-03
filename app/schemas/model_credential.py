"""Web-compatible BYOK status and write payloads."""

from typing import Literal

from pydantic import BaseModel, Field


class ModelCredentialUpsertRequest(BaseModel):
    apiKey: str = Field(repr=False)


class ModelCredentialStatus(BaseModel):
    providerId: str
    configured: bool
    maskedKey: str | None = None


class ModelCredentialTestRequest(BaseModel):
    apiKey: str | None = Field(default=None, repr=False)


class ModelCredentialTestResult(BaseModel):
    providerId: str
    modelId: str
    status: Literal["valid", "invalid", "unavailable"]
    message: str
