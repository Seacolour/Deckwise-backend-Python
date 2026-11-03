"""One LangGraph turn: context → model ↔ scoped tools → response."""

from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    limit_notice, make_context_node, make_model_node, make_tool_node, route_after_model,
)
from app.agent.state import AgentState


def build_agent_graph(
    model: BaseChatModel, tools: Sequence[BaseTool], mode: str,
    user_id: int, project_id: int,
    checkpointer: BaseCheckpointSaver | None = None,
    image_urls: Sequence[str] = (),
):
    builder = StateGraph(AgentState)
    builder.add_node("context", make_context_node(user_id, project_id))
    builder.add_node("model", make_model_node(model, tools, mode, image_urls))
    builder.add_node("tools", make_tool_node(tools))
    builder.add_node("limit", limit_notice)
    builder.add_edge(START, "context")
    builder.add_edge("context", "model")
    builder.add_conditional_edges("model", route_after_model, {
        "tools": "tools", "limit": "limit", END: END,
    })
    builder.add_edge("tools", "model")
    builder.add_edge("limit", END)
    return builder.compile(checkpointer=checkpointer)
