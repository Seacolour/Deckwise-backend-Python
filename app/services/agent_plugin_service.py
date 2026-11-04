"""Approved plugin catalog and user-scoped enablement."""

from dataclasses import dataclass

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.repositories import agent_plugin_repository, mcp_connection_repository
from app.schemas.agent_plugin import AgentPluginDTO
from app.services import skill_service, notion_mcp_connection_service


@dataclass(frozen=True)
class PluginDefinition:
    id: str
    kind: str
    name: str
    description: str
    default_enabled: bool
    source_url: str | None = None


def _catalog() -> dict[str, PluginDefinition]:
    docs = PluginDefinition(
        "docs-langchain", "mcp", "LangChain 文档 MCP",
        "搜索当前 LangChain、LangGraph 与 LangSmith 官方文档", False,
        "https://docs.langchain.com/use-these-docs",
    )
    notion = PluginDefinition(
        "notion", "mcp", "Notion", "授权后让 Agent 搜索和读取你的 Notion 页面", False,
        "https://developers.notion.com/guides/mcp/get-started-with-mcp",
    )
    skills = [PluginDefinition(
        f"skill:{item['name']}", "skill", item["name"], item["description"], True,
    ) for item in skill_service.list_skills()]
    return {item.id: item for item in [docs, notion, *skills]}


def list_plugins(user_id: int) -> list[AgentPluginDTO]:
    with session_scope() as db:
        overrides = agent_plugin_repository.list_overrides(db, user_id)
    notion_status, workspace_name = notion_mcp_connection_service.connection_status(user_id)
    return [AgentPluginDTO(
        id=item.id, kind=item.kind, name=item.name,
        description=item.description,
        enabled=overrides.get(item.id, item.default_enabled)
                and (item.id != "notion" or notion_status == "connected"),
        sourceUrl=item.source_url,
        connectionStatus=notion_status if item.id == "notion" else None,
        workspaceName=workspace_name if item.id == "notion" else None,
    ) for item in _catalog().values()]


def enabled_plugin_ids(user_id: int) -> set[str]:
    return {item.id for item in list_plugins(user_id) if item.enabled}


def update_plugin(user_id: int, plugin_id: str, enabled: bool) -> AgentPluginDTO:
    definition = _catalog().get(plugin_id)
    if definition is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "插件不存在")
    with session_scope() as db:
        if plugin_id == "notion" and enabled:
            connection = mcp_connection_repository.find(db, user_id, lock=True)
            if connection is None or connection["status"] != "connected":
                raise BusinessError(409, ErrorCode.REVISION_CONFLICT, "请先连接 Notion")
        agent_plugin_repository.set_enabled(db, user_id, plugin_id, enabled)
    notion_status, workspace_name = (notion_mcp_connection_service.connection_status(user_id)
                                     if plugin_id == "notion" else (None, None))
    return AgentPluginDTO(
        id=definition.id, kind=definition.kind, name=definition.name,
        description=definition.description, enabled=enabled,
        sourceUrl=definition.source_url,
        connectionStatus=notion_status,
        workspaceName=workspace_name,
    )
