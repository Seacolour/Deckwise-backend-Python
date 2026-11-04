"""A bounded LangChain RAG tool backed by LangGraph PostgresStore."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.services import rag_service


def make_semantic_file_search_tool(user_id: int, project_id: int) -> BaseTool:
    @tool
    async def semantic_file_search(query: str, limit: int = 3, cache_key: str | None = None) -> str:
        """Find relevant parsed file fragments by meaning in the current project.

        Provide cache_key to search only one file. Results include a snippet and
        fragment_index; use file_content_read for more surrounding source text.
        Requires the user's OpenRouter Key for BGE-M3 embeddings.
        """
        try:
            result = await rag_service.search_project_files(user_id, project_id, query, limit, cache_key)
        except BusinessError as error:
            return json.dumps({"success": False, "error": error.message,
                               "code": int(error.code)}, ensure_ascii=False)
        return json.dumps({"success": True, **result}, ensure_ascii=False)

    return semantic_file_search
