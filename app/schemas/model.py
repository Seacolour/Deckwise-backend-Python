"""Web model picker contract for callable models."""

from pydantic import BaseModel


class AvailableModelDTO(BaseModel):
    id: str
    providerId: str
    displayName: str
    description: str | None = None
    requiredCapability: str | None = None
    askSupported: bool
    agentSupported: bool
    imageSupported: bool = False
