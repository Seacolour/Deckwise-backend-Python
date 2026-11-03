"""LangChain model-facing document and file tools."""
"""Factories for project-scoped LangChain tools."""

from langchain_core.tools import BaseTool

from app.agent.tools.document_create import make_document_create_tool
from app.agent.tools.document_diff import make_document_diff_tool
from app.agent.tools.document_edit_session import DocumentEditSession
from app.agent.tools.document_locate import make_document_locate_tool
from app.agent.tools.document_read import make_document_read_tool
from app.agent.tools.document_save import make_document_save_tool
from app.agent.tools.file_content_read import make_file_content_read_tool
from app.agent.tools.file_list import make_file_list_tool
from app.agent.tools.json_read import make_json_read_tools


def tools_for_project(user_id: int, project_id: int, mode: str) -> list[BaseTool]:
    edit_sessions: dict[int, DocumentEditSession] = {}
    tools = [
        make_file_list_tool(user_id, project_id),
        make_file_content_read_tool(user_id, project_id),
        make_document_read_tool(user_id, project_id, edit_sessions),
        *make_json_read_tools(user_id, project_id),
    ]
    if mode == "AGENT":
        tools.extend([
            make_document_create_tool(user_id, project_id),
            make_document_locate_tool(user_id, project_id, edit_sessions),
            make_document_diff_tool(edit_sessions),
            make_document_save_tool(user_id, project_id, edit_sessions),
        ])
    return tools
