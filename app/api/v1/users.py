"""Authenticated user profile endpoint consumed by the Web auth gate."""

from fastapi import APIRouter, Body, Depends, Request

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.core.security import COOKIE_NAME
from app.services.user_service import current_user
from app.schemas.checkin import CheckinRequest
from app.services import checkin_service
from app.schemas.model_credential import ModelCredentialTestRequest, ModelCredentialUpsertRequest
from app.services import model_credential_service, model_credential_test_service

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/get/login")
def get_login_user(request: Request) -> dict[str, object]:
    return ok(current_user(request.cookies.get(COOKIE_NAME)).model_dump())


@router.get("/checkin/status")
def checkin_status(user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(checkin_service.get_status(user_id).model_dump(mode="json"))


@router.post("/checkin")
def checkin(
    request: Request, body: CheckinRequest | None = Body(default=None),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    result = checkin_service.checkin(
        user_id, body, request.headers.get("x-app-platform"),
        request.headers.get("x-app-version"),
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return ok(result.model_dump(mode="json"))


@router.get("/model-credentials")
def list_model_credentials(user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok([item.model_dump(mode="json") for item in model_credential_service.list_status(user_id)])


@router.put("/model-credentials/{provider_id}")
def upsert_model_credential(
    provider_id: str, body: ModelCredentialUpsertRequest,
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(model_credential_service.upsert(user_id, provider_id, body.apiKey).model_dump(mode="json"))


@router.delete("/model-credentials/{provider_id}")
def delete_model_credential(provider_id: str, user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(model_credential_service.delete(user_id, provider_id))


@router.post("/model-credentials/{provider_id}/test")
async def test_model_credential(
    provider_id: str, body: ModelCredentialTestRequest | None = Body(default=None),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    result = await model_credential_test_service.test_credential(
        user_id, provider_id, body.apiKey if body else None,
    )
    return ok(result.model_dump(mode="json"))
