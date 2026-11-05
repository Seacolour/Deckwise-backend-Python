"""Rebuildable user-memory semantic index and bounded cross-session recall."""

import asyncio
import logging

from langgraph.store.base import IndexConfig
from langgraph.store.postgres import AsyncPostgresStore

from app.db.checkpoint import checkpoint_conninfo
from app.services import embedding_service, model_credential_service, user_memory_service

logger = logging.getLogger("uvicorn.error")
MAX_CONTEXT_CHARS = 3_200
MAX_PROFILE_CHARS = 900
MAX_MEMORY_CHARS = 650
MAX_RECALLED = 3


def _namespace(user_id: int) -> tuple[str, ...]:
    return ("deckwise", "users", str(user_id), "memories", "bge-m3-v1")


async def _semantic_hits(user_id: int, query: str, memories: list) -> list:
    namespace = _namespace(user_id)
    index = IndexConfig(embed=embedding_service.openrouter_bge_embeddings(user_id),
                        dims=embedding_service.EMBEDDING_DIMENSIONS, fields=["text"])
    async with AsyncPostgresStore.from_conn_string(checkpoint_conninfo(), index=index) as store:
        await store.setup()
        existing = {item.key: item.value for item in await store.asearch(namespace, limit=500)
                    if item.namespace == namespace}
        current = {memory.id: {"text": memory.title + "\n" + memory.content,
                               "title": memory.title, "content": memory.content,
                               "source": memory.source}
                   for memory in memories}
        await asyncio.gather(*(store.adelete(namespace, key) for key in existing.keys() - current.keys()))
        await asyncio.gather(*(store.aput(namespace, key, value) for key, value in current.items()
                               if existing.get(key) != value))
        if not current:
            return []
        hits = await store.asearch(namespace, query=query, limit=MAX_RECALLED)
    by_id = {memory.id: memory for memory in memories}
    return [by_id[hit.key] for hit in hits if hit.key in by_id]


async def relevant_context(user_id: int, query: str) -> str:
    memories = await asyncio.to_thread(user_memory_service.list_memories, user_id)
    profile = next((item for item in memories
                    if item.title == user_memory_service.PROFILE_MEMORY_TITLE), None)
    ordinary = [item for item in memories if item.id != (profile.id if profile else None)]
    selected = ordinary[:MAX_RECALLED]
    if query.strip() and "openrouter" in await asyncio.to_thread(
        model_credential_service.configured_providers, user_id,
    ):
        try:
            selected = await _semantic_hits(user_id, query, ordinary)
        except Exception as error:
            logger.warning("memory semantic recall failed user_id=%s exception=%s",
                           user_id, type(error).__name__)
            selected = ordinary[:MAX_RECALLED]
    lines = []
    if profile:
        lines.append(f"用户画像：{profile.content[:MAX_PROFILE_CHARS]}")
    lines.extend(f"- {item.title[:120]}：{item.content[:MAX_MEMORY_CHARS]}" for item in selected)
    return "\n".join(lines)[:MAX_CONTEXT_CHARS]
