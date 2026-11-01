"""Authenticated model picker endpoint."""

from fastapi import APIRouter, Depends

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.services.model_service import available_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/available")
def list_available_models(_user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok([item.model_dump(mode="json") for item in available_models()])
