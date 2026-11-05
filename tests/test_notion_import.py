"""A Notion import is a user-selected, project-owned Markdown snapshot."""

import asyncio
import json

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.schemas.file import FileUploadItemDTO
from app.services import notion_import_service

PAGE_ID = "0123456789abcdef0123456789abcdef"
PAGE_URL = f"https://app.notion.com/p/{PAGE_ID}?pvs=204"


def _result(content: str = "# 标题\n\n正文") -> list[dict]:
    return [{"type": "text", "text": json.dumps({
        "metadata": {"type": "page"}, "title": "研究/笔记", "url": PAGE_URL,
        "text": f'<page url="{PAGE_URL}">\n<content>\n{content}\n</content>\n</page>',
        "page_last_edited_at": "2026-11-05T01:00:00Z",
    }, ensure_ascii=False)}]


def test_page_reference_and_snapshot_body_are_bounded() -> None:
    assert notion_import_service._page_id(PAGE_URL) == PAGE_ID
    assert notion_import_service._page_id(PAGE_ID) == PAGE_ID
    with pytest.raises(BusinessError):
        notion_import_service._page_id("https://example.com/p/" + PAGE_ID)
    title, url, content, edited = notion_import_service._parse_fetch(_result(), PAGE_ID)
    assert (title, url, content, edited) == (
        "研究/笔记", PAGE_URL, "# 标题\n\n正文", "2026-11-05T01:00:00Z",
    )
    assert notion_import_service._filename(title, PAGE_ID) == "研究-笔记.md"
    with pytest.raises(BusinessError):
        notion_import_service._parse_fetch(_result(), "0" * 32)
    with pytest.raises(BusinessError):
        notion_import_service._parse_fetch(_result(""), PAGE_ID)


def test_import_checks_project_then_uses_read_tool_and_file_service(monkeypatch) -> None:
    observed: list[tuple] = []

    def owned(user_id: int, project_id: int) -> None:
        observed.append(("project", user_id, project_id))

    class Fetch:
        name = "notion-fetch"

        async def ainvoke(self, args):
            observed.append(("fetch", args["id"]))
            return _result()

    class Adapter:
        def __init__(self, _client):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def list_tools(self):
            return [Fetch()]

    def upload(user_id, project_id, file, **kwargs):
        observed.append(("upload", user_id, project_id, file.filename,
                         file.file.read().decode(), kwargs))
        return FileUploadItemDTO(sourceFileId="14", fileId="14", fileName=file.filename,
                                 fileSize=20, sizeBytes=20, mimeType="text/markdown; charset=utf-8",
                                 objectKey="demo/notion.md", cacheKey="a" * 64, totalFragments=1)

    monkeypatch.setattr(notion_import_service, "_owned_project", owned)
    monkeypatch.setattr(notion_import_service.notion_mcp_connection_service, "access_token",
                        lambda _user_id: "private-token")
    import langchain.mcp
    monkeypatch.setattr(langchain.mcp, "MCPAdapter", Adapter)
    monkeypatch.setattr(notion_import_service.file_service, "upload_one", upload)
    result = asyncio.run(notion_import_service.import_page(7, 11, PAGE_URL))
    assert result.pageId == PAGE_ID and result.file.sourceFileId == "14"
    assert observed[0] == ("project", 7, 11)
    assert observed[1] == ("fetch", PAGE_ID)
    assert observed[2][:5] == ("upload", 7, 11, "研究-笔记.md", "# 标题\n\n正文")
    assert observed[2][5] == {
        "source_type": "notion", "source_id": PAGE_ID, "source_url": PAGE_URL,
    }


def test_foreign_project_is_rejected_before_notion_access(monkeypatch) -> None:
    def reject(_user_id, _project_id):
        raise BusinessError(404, ErrorCode.NOT_FOUND, "项目不存在")

    monkeypatch.setattr(notion_import_service, "_owned_project", reject)
    monkeypatch.setattr(notion_import_service.notion_mcp_connection_service, "access_token",
                        lambda _user_id: (_ for _ in ()).throw(AssertionError("Notion must not be called")))
    with pytest.raises(BusinessError) as error:
        asyncio.run(notion_import_service.import_page(7, 11, PAGE_ID))
    assert error.value.status == 404
