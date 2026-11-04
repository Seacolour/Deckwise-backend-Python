"""Bind only bounded, user-scoped read tools from a Notion MCP catalog."""

import asyncio
import json
from collections.abc import Sequence

from langchain_core.tools import BaseTool, tool

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.services import agent_plugin_service

READ_TOOL_NAMES = frozenset({"notion-search", "notion-fetch"})


def _text(result: object, limit: int) -> str:
    if isinstance(result, list):
        value = "\n".join(str(part.get("text", "")) for part in result
                          if isinstance(part, dict) and part.get("type") == "text")
    elif isinstance(result, str):
        value = result
    else:
        value = json.dumps(result, ensure_ascii=False, default=str)
    return value[:limit] + ("\n<结果已截断>" if len(value) > limit else "")


def make_notion_read_tools(user_id: int, discovered: Sequence[BaseTool]) -> list[BaseTool]:
    selected = {item.name: item for item in discovered if item.name in READ_TOOL_NAMES}
    if set(selected) != READ_TOOL_NAMES:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "Notion MCP 未提供所需读取工具")

    async def allowed() -> bool:
        return "notion" in await asyncio.to_thread(agent_plugin_service.enabled_plugin_ids, user_id)

    @tool
    async def notion_search(query: str) -> str:
        """Search only the current user's authorized Notion pages. Use for Notion questions; do not send local project text."""
        if not await allowed():
            return json.dumps({"success": False, "error": "Notion 插件已关闭或连接失效"}, ensure_ascii=False)
        query = query.strip()
        if not query or len(query) > 200:
            return json.dumps({"success": False, "error": "搜索词须为 1–200 字符"}, ensure_ascii=False)
        try:
            result = await selected["notion-search"].ainvoke({"query": query})
        except Exception:
            return json.dumps({"success": False, "error": "Notion 搜索暂时不可用"}, ensure_ascii=False)
        return json.dumps({"success": True, "content": _text(result, 6_000)}, ensure_ascii=False)

    @tool
    async def notion_fetch(id: str) -> str:
        """Read one authorized Notion page or database by URL or ID after searching. Cite its URL in the answer."""
        if not await allowed():
            return json.dumps({"success": False, "error": "Notion 插件已关闭或连接失效"}, ensure_ascii=False)
        identifier = id.strip()
        if not identifier or len(identifier) > 500:
            return json.dumps({"success": False, "error": "Notion 页面标识无效"}, ensure_ascii=False)
        try:
            result = await selected["notion-fetch"].ainvoke({"id": identifier})
        except Exception:
            return json.dumps({"success": False, "error": "Notion 页面读取暂时不可用"}, ensure_ascii=False)
        return json.dumps({"success": True, "content": _text(result, 12_000)}, ensure_ascii=False)

    return [notion_search, notion_fetch]
