"""User-owned memory, custom-rule, and profile endpoints."""

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.schemas.personalization import (
    UpdateCurrentUserRequest, UserMemoryCreateRequest, UserMemoryUpdateRequest, UserRuleRequest,
)
from app.services import user_memory_service, user_rule_service, user_service

router = APIRouter(prefix="/api/user", tags=["personalization"])


@router.get("/memories")
def list_memories(user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok([item.model_dump(mode="json") for item in user_memory_service.list_memories(user_id)])


@router.post("/memories")
def create_memory(body: UserMemoryCreateRequest,
                  user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_memory_service.create_memory(user_id, body.title, body.content).model_dump(mode="json"))


@router.put("/memories/{memory_id}")
def update_memory(body: UserMemoryUpdateRequest, memory_id: int = Path(gt=0),
                  user_id: int = Depends(current_user_id)) -> dict[str, object]:
    user_memory_service.update_memory(user_id, memory_id, body.title, body.content)
    return ok(True)


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: int = Path(gt=0),
                  user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_memory_service.delete_memory(user_id, memory_id))


@router.get("/rules")
def list_rules(user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok([item.model_dump(mode="json") for item in user_rule_service.list_rules(user_id)])


@router.post("/rules")
def create_rule(body: UserRuleRequest,
                user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_rule_service.create_rule(user_id, body.content).model_dump(mode="json"))


@router.put("/rules/{rule_id}")
def update_rule(body: UserRuleRequest, rule_id: int = Path(gt=0),
                user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_rule_service.update_rule(user_id, rule_id, body.content))


@router.put("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: int = Path(gt=0), enabled: bool = Query(...),
                user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_rule_service.toggle_rule(user_id, rule_id, enabled))


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int = Path(gt=0),
                user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_rule_service.delete_rule(user_id, rule_id))


@router.put("/update/my")
def update_my_profile(body: UpdateCurrentUserRequest,
                      user_id: int = Depends(current_user_id)) -> dict[str, object]:
    return ok(user_service.update_current_user_name(user_id, body.name).model_dump(mode="json"))
