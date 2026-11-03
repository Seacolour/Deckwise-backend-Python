"""Show PostgreSQL checkpoint recovery, pruning, and deletion with a fake model."""

import asyncio
import secrets
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.graph import build_agent_graph  # noqa: E402
from app.db.checkpoint import open_checkpointer, selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402


class EchoModel:
    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        latest = next(message for message in reversed(messages) if isinstance(message, HumanMessage))
        return AIMessage(content=f"已收到：{latest.content}")


@tool
def noop() -> str:
    """Do nothing; this tool lets the demo use the normal graph factory."""
    return "ok"


def checkpoint_count(thread_id: str) -> int:
    with get_engine().connect() as db:
        return db.scalar(text("SELECT count(*) FROM public.checkpoints WHERE thread_id = :id"), {"id": thread_id}) or 0


async def main() -> None:
    thread_id = f"deckwise:experiment:{secrets.token_hex(12)}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        async with open_checkpointer() as saver:
            graph = build_agent_graph(EchoModel(), [noop], "ASK", 0, 0, saver)
            first = await graph.ainvoke({"messages": [HumanMessage(content="第一轮")], "tool_rounds": 0}, config)
            assert len(first["messages"]) == 2
        before = checkpoint_count(thread_id)
        assert before > 1

        # A new saver and compiled graph simulate a process restart.
        async with open_checkpointer() as saver:
            graph = build_agent_graph(EchoModel(), [noop], "ASK", 0, 0, saver)
            restored = await graph.aget_state(config)
            assert len(restored.values["messages"]) == 2
            second = await graph.ainvoke({"messages": [HumanMessage(content="第二轮")], "tool_rounds": 0}, config)
            assert len(second["messages"]) == 4
            assert second["messages"][-1].content == "已收到：第二轮"
            await saver.aprune([thread_id], strategy="keep_latest")
            after = checkpoint_count(thread_id)
            assert after == 1
            assert len((await graph.aget_state(config)).values["messages"]) == 4
            print(f"checkpoint flow OK: restart restored 2 messages, rows {before}->{after} after prune")
            await saver.adelete_thread(thread_id)
            assert checkpoint_count(thread_id) == 0
    finally:
        # Safe if the test failed before its normal cleanup.
        async with open_checkpointer() as saver:
            await saver.adelete_thread(thread_id)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=selector_loop_factory)
