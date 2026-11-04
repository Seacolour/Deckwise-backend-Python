"""Check project-scoped pgvector retrieval without provider charges."""

import asyncio
import secrets
import sys
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langgraph.store.base import IndexConfig
from langgraph.store.postgres import AsyncPostgresStore
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.exceptions import BusinessError  # noqa: E402
from app.db.checkpoint import checkpoint_conninfo, selector_loop_factory  # noqa: E402
from app.db.session import get_engine, session_scope  # noqa: E402
from app.repositories import file_repository  # noqa: E402
from app.schemas.project import ProjectCreateRequest  # noqa: E402
from app.services import project_service, rag_service  # noqa: E402


class SyntheticEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(item) for item in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        head = [1.0, 0.0] if "苹果" in text or "水果" in text else [0.0, 1.0]
        return head + [0.0] * (rag_service.EMBEDDING_DIMENSIONS - 2)


async def check(user_id: int, other_user_id: int, project_id: int,
                fruit_key: str, vehicle_key: str) -> None:
    first = await rag_service.search_project_files(user_id, project_id, "哪些内容讲水果？")
    assert first["indexed_new"] == 2 and first["matches"][0]["cache_key"] == fruit_key, first
    second = await rag_service.search_project_files(user_id, project_id, "苹果相关内容")
    assert second["indexed_new"] == 0 and second["matches"][0]["cache_key"] == fruit_key, second
    narrowed = await rag_service.search_project_files(user_id, project_id, "汽车内容", cache_key=vehicle_key)
    assert narrowed["matches"] and all(item["cache_key"] == vehicle_key for item in narrowed["matches"])
    with session_scope() as db:
        db.execute(text("""
            UPDATE backend_data.project_file_links SET is_deleted = true
            WHERE project_id = :project_id AND file_id IN (
                SELECT id FROM backend_data.object_storage_files WHERE source_key = :cache_key
            )
        """), {"project_id": project_id, "cache_key": vehicle_key})
    after_unlink = await rag_service.search_project_files(user_id, project_id, "汽车内容")
    assert all(item["cache_key"] != vehicle_key for item in after_unlink["matches"])
    try:
        await rag_service.search_project_files(other_user_id, project_id, "苹果")
        raise AssertionError("cross-user semantic search succeeded")
    except BusinessError as error:
        assert error.status == 404
    print("RAG flow OK: persistent Store, scoped search, file filter, no re-embedding")


async def cleanup_index(user_id: int, project_id: int) -> None:
    namespace = rag_service._namespace(user_id, project_id)
    async with AsyncPostgresStore.from_conn_string(checkpoint_conninfo()) as store:
        for item in await store.asearch(namespace, limit=1000):
            if item.namespace == namespace:
                await store.adelete(namespace, item.key)


def main() -> None:
    suffix = secrets.token_hex(8)
    emails = [f"rag-check-{suffix}-a@example.test", f"rag-check-{suffix}-b@example.test"]
    with get_engine().begin() as db:
        user_ids = [db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email}) for email in emails]
    project_id: int | None = None
    original_embeddings = rag_service._embeddings
    rag_service._embeddings = lambda _user_id: SyntheticEmbeddings()
    try:
        project = project_service.create_project(user_ids[0], ProjectCreateRequest(name="RAG 联调"))
        project_id = int(project.id)
        fruit_key, vehicle_key = secrets.token_hex(32), secrets.token_hex(32)
        with session_scope() as db:
            for name, cache_key, content in (
                ("fruit.txt", fruit_key, "项目资料：苹果和梨等水果的分类。"),
                ("vehicle.txt", vehicle_key, "项目资料：汽车发动机与车轮的组成。"),
            ):
                file_id = file_repository.insert_file(
                    db, user_ids[0], cache_key, name, "rag-test", f"rag-test/{cache_key}",
                    len(content.encode()), "text/plain", ".txt", len(content), 1, "synthetic", None,
                )
                file_repository.insert_fragments(db, file_id, [content], ".txt")
                file_repository.attach_file(db, project_id, file_id, user_ids[0], name)
        asyncio.run(check(user_ids[0], user_ids[1], project_id, fruit_key, vehicle_key),
                    loop_factory=selector_loop_factory)
    finally:
        rag_service._embeddings = original_embeddings
        if project_id is not None:
            asyncio.run(cleanup_index(user_ids[0], project_id), loop_factory=selector_loop_factory)
        with get_engine().begin() as db:
            db.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
