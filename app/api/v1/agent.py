"""Conversation creation, history, and streaming endpoints."""

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import current_user_id
from app.core.responses import ok
from app.schemas.agent import SessionCreateRequest, UserMessageSendRequest
from app.services import agent_service, session_service

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/projects/{project_id}/create")
def create_session(
    body: SessionCreateRequest, project_id: int = Path(gt=0),
    user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(session_service.create_session(user_id, project_id, body).model_dump(mode="json"))


@router.get("/sessions/{session_id}/messages/after-seq")
def list_messages(
    session_id: int = Path(gt=0), after_seq: int = Query(default=0, alias="afterSeq", ge=0),
    limit: int = Query(default=500, ge=1, le=500), user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    rows = session_service.list_messages(user_id, session_id, after_seq, limit)
    return ok([row.model_dump(mode="json") for row in rows])


@router.post("/sessions/{session_id}/sendRPC")
async def send_message(
    request: Request, body: UserMessageSendRequest, session_id: int = Path(gt=0),
    user_id: int = Depends(current_user_id),
) -> StreamingResponse:
    stream = await agent_service.start_turn(user_id, session_id, body, request)
    return StreamingResponse(
        stream, media_type="text/event-stream",
        headers={"Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/abort")
async def abort_message(
    session_id: int = Path(gt=0), user_id: int = Depends(current_user_id),
) -> dict[str, object]:
    return ok(agent_service.abort_turn(user_id, session_id))
