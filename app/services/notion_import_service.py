"""Snapshot one authorized Notion page into the existing project file pipeline."""

import asyncio
import json
import re
from io import BytesIO
from urllib.parse import urlparse

from fastapi import UploadFile

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.schemas.notion import NotionPageImportDTO
from app.services import file_service, notion_mcp_connection_service
from app.services.notion_mcp_oauth_client import MCP_URL
from app.services.project_service import require_owned_project

_PAGE_ID = re.compile(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")
_NOTION_HOSTS = {"app.notion.com", "notion.so", "www.notion.so"}
_MAX_RESPONSE_CHARS = 1_200_000


def _page_id(value: str) -> str:
    value = value.strip()
    if _PAGE_ID.fullmatch(value):
        return value.replace("-", "").lower()
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in _NOTION_HOSTS:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "请输入 Notion 页面链接或 ID")
    matches = re.findall(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",
                         parsed.path)
    if not matches:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 页面链接缺少页面 ID")
    return matches[-1].replace("-", "").lower()


def _owned_project(user_id: int, project_id: int) -> None:
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)


def _parse_fetch(result: object, requested_page_id: str) -> tuple[str, str, str, str | None]:
    if not isinstance(result, list):
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面响应格式无效")
    blocks = [part.get("text") for part in result
              if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)]
    if len(blocks) != 1 or len(blocks[0]) > _MAX_RESPONSE_CHARS:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面过大或响应不完整")
    try:
        page = json.loads(blocks[0])
    except ValueError as error:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面响应格式无效") from error
    if not isinstance(page, dict) or not isinstance(page.get("metadata"), dict) or page["metadata"].get("type") != "page":
        raise BusinessError(422, ErrorCode.PARAMS_ERROR, "只能导入 Notion 页面")
    source_url = page.get("url")
    if not isinstance(source_url, str) or urlparse(source_url).hostname not in _NOTION_HOSTS:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面来源无效")
    if _page_id(source_url) != requested_page_id:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 返回了其他页面")
    if page.get("truncated") or page.get("has_more"):
        raise BusinessError(422, ErrorCode.PARAMS_ERROR, "Notion 页面内容不完整，暂不能导入")
    wrapped = page.get("text")
    if not isinstance(wrapped, str):
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面缺少正文")
    start = wrapped.find("<content>\n")
    end = wrapped.rfind("\n</content>")
    if start < 0 or end < start:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面正文格式无效")
    content = wrapped[start + len("<content>\n"):end].strip()
    if not content:
        raise BusinessError(422, ErrorCode.PARAMS_ERROR, "Notion 页面内容为空")
    title = str(page.get("title") or requested_page_id).strip()
    return title, source_url, content, page.get("page_last_edited_at")


def _filename(title: str, page_id: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", title).strip(" .")
    return f"{safe[:170] or page_id}.md"


async def import_page(user_id: int, project_id: int, page_id_or_url: str) -> NotionPageImportDTO:
    from fastmcp import Client
    from langchain.mcp import MCPAdapter

    page_id = _page_id(page_id_or_url)
    await asyncio.to_thread(_owned_project, user_id, project_id)
    token = await asyncio.to_thread(notion_mcp_connection_service.access_token, user_id)
    try:
        async with MCPAdapter(Client(MCP_URL, auth=token)) as adapter:
            fetch = next((item for item in await adapter.list_tools() if item.name == "notion-fetch"), None)
            if fetch is None:
                raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "Notion MCP 未提供页面读取工具")
            result = await fetch.ainvoke({"id": page_id})
    except BusinessError:
        raise
    except Exception as error:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 页面读取失败") from error
    title, source_url, content, edited_at = _parse_fetch(result, page_id)
    name = _filename(title, page_id)
    uploaded = await asyncio.to_thread(
        file_service.upload_one, user_id, project_id,
        UploadFile(file=BytesIO(content.encode("utf-8")), filename=name),
        source_type="notion", source_id=page_id, source_url=source_url,
    )
    return NotionPageImportDTO(pageId=page_id, pageUrl=source_url, title=title,
                               snapshotLastEditedAt=edited_at, file=uploaded)
