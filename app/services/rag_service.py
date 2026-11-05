"""Project-scoped semantic search over parsed file fragments."""

import asyncio

from langgraph.store.base import IndexConfig
from langgraph.store.postgres import AsyncPostgresStore

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.db.checkpoint import checkpoint_conninfo
from app.db.session import session_scope
from app.repositories import file_repository
from app.services import embedding_service, file_service
from app.services.project_service import require_owned_project

EMBEDDING_MODEL = embedding_service.EMBEDDING_MODEL
EMBEDDING_DIMENSIONS = embedding_service.EMBEDDING_DIMENSIONS
MAX_INDEX_FRAGMENTS = 120
MAX_QUERY_CHARS = 500


def _namespace(user_id: int, project_id: int) -> tuple[str, ...]:
    return ("deckwise", "users", str(user_id), "projects", str(project_id),
            "file-fragments", "bge-m3-v1")


def _embeddings(user_id: int):
    return embedding_service.openrouter_bge_embeddings(user_id)


async def search_project_files(
    user_id: int, project_id: int, query: str, limit: int = 3,
    cache_key: str | None = None,
) -> dict:
    query = query.strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "检索问题不能为空且最多 500 字符")
    if not 1 <= limit <= 5:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "最多返回 5 个检索片段")
    with session_scope() as db:
        require_owned_project(db, user_id, project_id)
        if cache_key and file_repository.find_project_file(db, user_id, project_id, cache_key=cache_key) is None:
            raise BusinessError(404, ErrorCode.NOT_FOUND, "文件不存在")
        fragments = file_repository.list_project_fragments_for_index(
            db, user_id, project_id, MAX_INDEX_FRAGMENTS + 1, cache_key,
        )
    if len(fragments) > MAX_INDEX_FRAGMENTS:
        raise BusinessError(413, ErrorCode.PARAMS_ERROR,
                            "检索范围超过 120 个分片，请指定单个文件的 cache_key")
    if not fragments:
        return {"matches": [], "indexed_new": 0, "total_fragments": 0}

    namespace = _namespace(user_id, project_id)
    index = IndexConfig(embed=_embeddings(user_id), dims=EMBEDDING_DIMENSIONS, fields=["text"])
    async with AsyncPostgresStore.from_conn_string(checkpoint_conninfo(), index=index) as store:
        await store.setup()
        existing = {item.key: item.value for item in await store.asearch(namespace, limit=1000)
                    if item.namespace == namespace}
        current = {}
        for fragment in fragments:
            key = f"{fragment['file_id']}:{fragment['fragment_index']}"
            current[key] = {
                "text": fragment["fragment_content"],
                "file_id": str(fragment["file_id"]),
                "file_name": fragment["file_name"],
                "cache_key": fragment["cache_key"],
                "fragment_index": fragment["fragment_index"],
            }
        if cache_key is None:
            await asyncio.gather(*(store.adelete(namespace, key) for key in existing.keys() - current.keys()))
        changed = [(key, value) for key, value in current.items() if existing.get(key) != value]
        await asyncio.gather(*(store.aput(namespace, key, value) for key, value in changed))
        hits = await store.asearch(namespace, query=query,
                                   filter={"cache_key": cache_key} if cache_key else None,
                                   limit=limit)
    matches = []
    for hit in hits:
        value = hit.value
        try:
            file_service.require_project_file(user_id, project_id, value["cache_key"])
        except BusinessError:
            continue
        matches.append({
            "file_id": value["file_id"], "file_name": value["file_name"],
            "cache_key": value["cache_key"], "fragment_index": value["fragment_index"],
            "score": round(hit.score, 4) if hit.score is not None else None,
            "snippet": value["text"][:800],
        })
    return {"matches": matches, "indexed_new": len(changed),
            "total_fragments": len(fragments)}
