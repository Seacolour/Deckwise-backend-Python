"""Run one scoped LangGraph turn and bridge its events to Web SSE."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import Request
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.agent.graph import build_agent_graph
from app.agent.tools import tools_for_project
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.session import session_scope
from app.db.checkpoint import checkpoint_thread_id
from app.schemas.agent import UserMessageSendRequest
from app.services import document_service, file_service, model_service, session_service

logger = logging.getLogger("uvicorn.error")
_active_runs: dict[tuple[int, int], asyncio.Event] = {}


def _frame(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n\n"


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(part.get("text", "") for part in value if isinstance(part, dict) and part.get("type") == "text")
    return ""


def abort_turn(user_id: int, session_id: int) -> bool:
    with session_scope() as db:
        session_service.require_owned_session(db, user_id, session_id)
    active = _active_runs.get((user_id, session_id))
    if active:
        active.set()
    return True


async def start_turn(
    user_id: int, session_id: int, body: UserMessageSendRequest, request: Request,
) -> AsyncIterator[str]:
    message = body.message.strip()
    if not message:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "消息不能为空")
    if body.imageCacheKeys:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "图片附件暂未接入当前 Agent")

    model = model_service.resolve_chat_model(body.model)
    key = (user_id, session_id)
    if key in _active_runs:
        raise BusinessError(409, ErrorCode.REVISION_CONFLICT, "当前会话正在处理上一条消息")

    with session_scope() as db:
        session = session_service.require_owned_session(db, user_id, session_id)
        project_id = session.project_id
    for cache_key in body.fileCacheKeys:
        file_service.require_project_file(user_id, project_id, cache_key)
    context = body.clientContext
    active_document_id = context.activeDocument.documentId if context and context.activeDocument else None
    referenced_document_ids = context.referencedDocumentIds if context else []
    for document_id in ([active_document_id] if active_document_id else []) + referenced_document_ids:
        document_service.get_document(user_id, document_id, False, expected_project_id=project_id)

    tools = tools_for_project(user_id, project_id, body.mode)
    checkpointer = getattr(request.app.state, "checkpointer", None)
    graph = build_agent_graph(model, tools, body.mode, user_id, project_id, checkpointer)
    graph_config: dict = {"recursion_limit": 20}
    include_history = True
    if checkpointer is not None:
        graph_config["configurable"] = {"thread_id": checkpoint_thread_id(user_id, session_id)}
        snapshot = await graph.aget_state(graph_config)
        include_history = not bool(snapshot.values.get("messages"))
    stop_event = asyncio.Event()
    _active_runs[key] = stop_event
    try:
        project_id, history = session_service.prepare_turn(
            user_id, session_id, message, include_history=include_history,
        )
    except BaseException:
        _active_runs.pop(key, None)
        raise

    async def stream() -> AsyncIterator[str]:
        events: list[tuple[str, str, str]] = []
        call_names: dict[str, str] = {}
        round_text = ""
        run_status = "aborted"
        error_message: str | None = None
        messages = [HumanMessage(content=text) if role == "user" else AIMessage(content=text)
                    for role, text in history]
        messages.append(HumanMessage(content=message))

        def append_text(delta: str) -> None:
            if events and events[-1][0:2] == ("assistant", "text"):
                role, kind, previous = events[-1]
                events[-1] = (role, kind, previous + delta)
            else:
                events.append(("assistant", "text", delta))

        try:
            async for chunk in graph.astream(
                {"messages": messages, "active_document_id": active_document_id,
                 "referenced_document_ids": referenced_document_ids,
                 "attached_file_keys": body.fileCacheKeys, "tool_rounds": 0},
                stream_mode=["messages", "updates"], version="v2",
                config=graph_config,
            ):
                if stop_event.is_set() or await request.is_disconnected():
                    break
                if chunk["type"] == "messages":
                    token, metadata = chunk["data"]
                    if metadata.get("langgraph_node") == "model" and isinstance(token, AIMessageChunk):
                        delta = _text(token.content)
                        if delta:
                            round_text += delta
                            append_text(delta)
                            yield _frame({"type": "text", "payload": delta})
                elif chunk["type"] == "updates":
                    update = chunk["data"]
                    if "model" in update:
                        ai = update["model"]["messages"][-1]
                        if isinstance(ai, AIMessage):
                            fallback = _text(ai.content)
                            if fallback and not round_text:
                                append_text(fallback)
                                yield _frame({"type": "text", "payload": fallback})
                            for call in ai.tool_calls:
                                call_names[call["id"]] = call["name"]
                                frame = {
                                    "type": "tool_call", "name": call["name"],
                                    "call_id": call["id"],
                                    "arguments_json": json.dumps(call["args"], ensure_ascii=False),
                                }
                                payload = json.dumps(frame, ensure_ascii=False)
                                events.append(("tool", "tool_output", payload))
                                yield _frame(frame)
                        round_text = ""
                    elif "tools" in update:
                        for tool_message in update["tools"]["messages"]:
                            if not isinstance(tool_message, ToolMessage):
                                continue
                            frame = {
                                "type": "tool_result", "name": tool_message.name or call_names.get(tool_message.tool_call_id, "tool"),
                                "call_id": tool_message.tool_call_id,
                                "result_json": _text(tool_message.content),
                            }
                            payload = json.dumps(frame, ensure_ascii=False)
                            events.append(("tool", "tool_output", payload))
                            yield _frame(frame)
                    elif "limit" in update:
                        notice = _text(update["limit"]["messages"][-1].content)
                        if notice:
                            append_text(notice)
                            yield _frame({"type": "text", "payload": notice})
            else:
                run_status = "final"
        except asyncio.CancelledError:
            raise
        except Exception as error:
            run_status = "error"
            error_message = "模型处理失败，请稍后重试"
            logger.warning("agent run failed session_id=%s exception=%s", session_id, type(error).__name__)
        finally:
            try:
                session_service.persist_turn_events(user_id, session_id, events, run_status)
            finally:
                _active_runs.pop(key, None)

        if error_message:
            yield "event: error\ndata: " + json.dumps({"message": error_message}, ensure_ascii=False) + "\n\n"
        elif run_status == "aborted":
            yield "event: abort\ndata: stopped\n\n"
        else:
            yield "event: done\ndata: [DONE]\n\n"

    return stream()
