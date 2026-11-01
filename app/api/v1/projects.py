"""Project, session-list, and file-list endpoints consumed by the Web workbench."""

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.schemas.pagination import PageRequest
from app.schemas.project import ProjectCreateRequest, ProjectListQuery
from app.services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("/list")
def list_projects(body: ProjectListQuery, user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(project_service.list_projects(user_id, body).model_dump(by_alias=True, mode="json"))


@router.post("/create")
def create_project(body: ProjectCreateRequest, user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(project_service.create_project(user_id, body).model_dump(mode="json"))


@router.post("/{project_id}/list")
def list_sessions(
    project_id: int = Path(gt=0), body: PageRequest | None = None,
    archived: bool | None = Query(default=None), user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    page = project_service.list_sessions(user_id, project_id, body or PageRequest(), archived)
    return ok(page.model_dump(by_alias=True, mode="json"))


@router.get("/{project_id}/files")
def list_files(project_id: int = Path(gt=0), user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok([item.model_dump(mode="json") for item in project_service.list_project_files(user_id, project_id)])
