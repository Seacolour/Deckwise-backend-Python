"""Per-turn graph state; durable conversation history lives in PostgreSQL."""

from typing import NotRequired

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    active_document_id: NotRequired[int | None]
    referenced_document_ids: NotRequired[list[int]]
    attached_file_keys: NotRequired[list[str]]
    context_note: NotRequired[str]
    tool_rounds: NotRequired[int]
