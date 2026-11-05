"""Explicit Notion page snapshot import into an owned project."""

from fastapi import APIRouter, Depends

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.schemas.notion import NotionPageImportRequest
from app.services import notion_import_service

router = APIRouter(prefix="/api/notion", tags=["notion"])


@router.post("/pages/import")
async def import_notion_page(body: NotionPageImportRequest,
                             user_id: int = Depends(current_user_id)) -> dict[str, object]:
    result = await notion_import_service.import_page(user_id, body.projectId, body.pageIdOrUrl)
    return ok(result.model_dump(mode="json"))
