"""State fields for the future document-editing LangGraph workflow."""

from typing import NotRequired

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    active_document_id: NotRequired[str | None]
    document_revision: NotRequired[int | None]
