"""LangChain tool for bounded reads of parsed project files."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.services import file_service


def make_file_content_read_tool(user_id: int, project_id: int) -> BaseTool:
    @tool
    def file_content_read(cache_key: str, start_index: int = 0, limit: int = 2) -> str:
        """Read 1–5 parsed text fragments from a file in this project.

        Use file_list to find a cache_key. Continue at the next start_index
        when hasMore is true; avoid loading the entire file at once.
        """
        try:
            page = file_service.read_file_fragments(user_id, project_id, cache_key, start_index, limit)
        except BusinessError as error:
            return json.dumps({"success": False, "error": error.message, "code": int(error.code)}, ensure_ascii=False)
        return json.dumps({"success": True, **page.model_dump(mode="json")}, ensure_ascii=False)

    return file_content_read
