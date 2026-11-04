"""Small user-scoped MCP and Skill plugin catalog contracts."""

from typing import Literal

from pydantic import BaseModel


class AgentPluginDTO(BaseModel):
    id: str
    kind: Literal["mcp", "skill"]
    name: str
    description: str
    enabled: bool
    sourceUrl: str | None = None
    connectionStatus: Literal["disconnected", "authorizing", "connected", "reconnect_required"] | None = None
    workspaceName: str | None = None


class AgentPluginUpdateRequest(BaseModel):
    enabled: bool


class NotionMcpCallbackRequest(BaseModel):
    code: str
    state: str
