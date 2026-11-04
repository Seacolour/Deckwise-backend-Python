"""Bounded read-only queries to the public LangChain documentation MCP."""

import re

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

DOCS_MCP_URL = "https://docs.langchain.com/mcp"
MAX_QUERY_CHARS = 300
MAX_EXCERPT_CHARS = 1_800
MAX_RESULTS = 3
_RESULT_PATTERN = re.compile(r"^Title: (?P<title>[^\n]+)\nLink: (?P<url>https://docs\.langchain\.com/[^\n]+).*?\nContent: (?P<content>.*)", re.S)


async def search_docs(query: str) -> list[dict[str, str]]:
    query = query.strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "文档检索问题不能为空且最多 300 字符")
    from langchain.mcp import MCPAdapter

    async with MCPAdapter(DOCS_MCP_URL) as adapter:
        tools = await adapter.list_tools()
        search = next((item for item in tools if item.name == "search_docs_by_lang_chain"), None)
        if search is None:
            raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "文档 MCP 未提供搜索工具")
        raw = await search.ainvoke({"query": query})
    texts = [item.get("text", "") for item in raw if isinstance(item, dict)
             and item.get("type") == "text"] if isinstance(raw, list) else [str(raw)]
    parsed = []
    for value in texts:
        match = _RESULT_PATTERN.match(value)
        if match:
            parsed.append({"title": match.group("title"), "url": match.group("url"),
                           "excerpt": match.group("content")[:MAX_EXCERPT_CHARS]})
    python_results = [item for item in parsed if "/oss/python/" in item["url"]]
    return (python_results or parsed)[:MAX_RESULTS]
