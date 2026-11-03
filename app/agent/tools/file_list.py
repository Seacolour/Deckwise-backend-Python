"""Project-scoped document and uploaded-file discovery tool."""

import json
from pathlib import Path

from langchain_core.tools import BaseTool, tool

from app.services import document_service, project_service


def make_file_list_tool(user_id: int, project_id: int) -> BaseTool:
    @tool
    def file_list() -> str:
        """List document IDs and file names in the current project.

        Use document_read with a listed document ID to see its current draft.
        """
        documents = document_service.list_documents(user_id, project_id, 0, 100)
        files = project_service.list_project_files(user_id, project_id)
        return json.dumps({
            "documents": [
                {"document_id": item.id, "title": item.title, "version": item.version}
                for item in documents
            ],
            "files": [
                {"file_id": item.id, "cache_key": item.cacheKey,
                 "name": item.fileName, "document_id": item.documentId,
                 "composite_tools": (["json_structure_read", "json_subtree_read", "file_content_read"]
                                     if Path(item.fileName).suffix.lower() == ".json"
                                     else [] if Path(item.fileName).suffix.lower() in
                                     {".png", ".jpg", ".jpeg", ".webp", ".gif"}
                                     else ["file_content_read"])}
                for item in files
            ],
        }, ensure_ascii=False)

    return file_list
