"""LangChain model-facing document and file tools."""
"""Factories for project-scoped LangChain tools."""

from langchain_core.tools import BaseTool

from app.agent.tools.document_read import make_document_read_tool
from app.agent.tools.document_save import make_document_save_tool
from app.agent.tools.file_list import make_file_list_tool


def tools_for_project(user_id: int, project_id: int, mode: str) -> list[BaseTool]:
    read_versions: dict[int, int] = {}
    tools = [make_file_list_tool(user_id, project_id), make_document_read_tool(user_id, project_id, read_versions)]
    if mode == "AGENT":
        tools.append(make_document_save_tool(user_id, project_id, read_versions))
    return tools
