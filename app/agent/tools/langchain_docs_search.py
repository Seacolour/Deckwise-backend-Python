"""Expose only read-only LangChain documentation search from the MCP server."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.services import mcp_docs_service


def make_langchain_docs_search_tool() -> BaseTool:
    @tool
    async def langchain_docs_search(query: str) -> str:
        """Search current public LangChain and LangGraph docs via a read-only MCP tool.

        Use for framework questions only. Do not send private project content.
        Results include documentation URLs for citation.
        """
        try:
            results = await mcp_docs_service.search_docs(query)
        except BusinessError as error:
            return json.dumps({"success": False, "error": error.message}, ensure_ascii=False)
        except Exception:
            return json.dumps({"success": False, "error": "LangChain 文档 MCP 暂时不可用"}, ensure_ascii=False)
        return json.dumps({"success": True, "results": results}, ensure_ascii=False)

    return langchain_docs_search
