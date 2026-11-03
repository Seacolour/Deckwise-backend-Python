"""Project-scoped LangChain tools for bounded structured JSON reads."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.services import file_service, json_structure_service


def make_json_read_tools(user_id: int, project_id: int) -> list[BaseTool]:
    def load(file_id: int) -> object:
        return file_service.read_project_json(user_id, project_id, file_id)

    def failure(error: BusinessError) -> str:
        return json.dumps({"success": False, "code": int(error.code), "error": error.message}, ensure_ascii=False)

    @tool
    def json_structure_read(file_id: int, path: str = "", max_depth: int = 2,
                            max_keys: int = 20, sample_array_items: int = 3) -> str:
        """Inspect the structure of a project JSON file at an RFC 6901 path.

        An empty path means root. Use the returned child paths with
        json_subtree_read; increase max_depth only for narrow paths.
        """
        try:
            result = json_structure_service.structure(
                load(file_id), path, max_depth, max_keys, sample_array_items,
            )
        except BusinessError as error:
            return failure(error)
        return json.dumps({"success": True, "file_id": file_id, **result}, ensure_ascii=False)

    @tool
    def json_subtree_read(file_id: int, path: str = "", max_bytes: int = 12_000,
                          max_nodes: int = 400) -> str:
        """Read one bounded JSON subtree using a path from json_structure_read.

        An empty path means root. Large subtrees are rejected; navigate to
        a narrower path instead of returning truncated JSON.
        """
        try:
            result = json_structure_service.subtree(load(file_id), path, max_bytes, max_nodes)
        except BusinessError as error:
            return failure(error)
        return json.dumps({"success": True, "file_id": file_id, **result}, ensure_ascii=False)

    return [json_structure_read, json_subtree_read]
