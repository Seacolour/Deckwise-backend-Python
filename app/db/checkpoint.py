"""Optional PostgreSQL checkpoint storage for the LangGraph learning path."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from app.core.config import database_settings, setting


def checkpoint_enabled() -> bool:
    return (setting("DECKWISE_CHECKPOINT_ENABLED", "false") or "false").lower() == "true"


def selector_loop_factory(use_subprocess: bool = False) -> asyncio.AbstractEventLoop:
    """Use a psycopg-compatible loop on Windows without deprecated event-loop policies."""
    return asyncio.SelectorEventLoop()


def checkpoint_thread_id(user_id: int, session_id: int) -> str:
    return f"deckwise:user:{user_id}:session:{session_id}"


def checkpoint_conninfo() -> str:
    settings = database_settings()
    params = {
        "host": settings.host,
        "port": settings.port,
        "dbname": settings.name,
        "user": settings.user,
    }
    if settings.password:
        params["password"] = settings.password
    return make_conninfo(**params)


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(checkpoint_conninfo()) as saver:
        # Safe to repeat for this local demo; the saver manages its own tables
        # in the database's default schema, separate from backend_data.
        await saver.setup()
        yield saver
