"""User and Agent memory CRUD, semantic recall, and isolation on local services."""

import asyncio
import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
from langchain_core.embeddings import Embeddings
from langgraph.store.postgres import AsyncPostgresStore
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.tools.user_memory import make_manage_user_memory_tool  # noqa: E402
from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import checkpoint_conninfo, selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services import embedding_service, memory_retrieval_service, model_credential_service  # noqa: E402


class SyntheticEmbeddings(Embeddings):
    def _vector(self, value: str) -> list[float]:
        first = [1.0, 0.0] if "简洁" in value or "短句" in value else [0.0, 1.0]
        return first + [0.0] * (embedding_service.EMBEDDING_DIMENSIONS - 2)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(value) for value in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

async def clear_store(user_ids: list[int]) -> None:
    async with AsyncPostgresStore.from_conn_string(checkpoint_conninfo()) as store:
        for user_id in user_ids:
            namespace = memory_retrieval_service._namespace(user_id)
            for item in await store.asearch(namespace, limit=500):
                await store.adelete(namespace, item.key)


async def indexed_keys(user_id: int) -> set[str]:
    async with AsyncPostgresStore.from_conn_string(checkpoint_conninfo()) as store:
        return {item.key for item in await store.asearch(memory_retrieval_service._namespace(user_id), limit=500)}


def main() -> None:
    marker = secrets.token_hex(6)
    emails = [f"memory-check-{marker}-{suffix}@example.test" for suffix in ("a", "b")]
    tokens = [new_session_token(), new_session_token()]
    with get_engine().begin() as db:
        user_ids = [db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email}) for email in emails]
    original_embeddings = embedding_service.openrouter_bge_embeddings
    original_providers = model_credential_service.configured_providers
    embedding_service.openrouter_bge_embeddings = lambda _user_id: SyntheticEmbeddings()
    model_credential_service.configured_providers = lambda _user_id: {"openrouter"}
    try:
        for token, user_id in zip(tokens, user_ids):
            auth_redis_repository.create_web_session(token, user_id)
        headers = [{"cookie": f"{COOKIE_NAME}={token}"} for token in tokens]
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            assert client.get("/api/user/memories").status_code == 401
            assert client.get("/api/user/memories", headers=headers[0]).json()["data"] == []
            name = client.put("/api/user/update/my", headers=headers[0], json={"name": "记忆联调用户"})
            assert name.status_code == 200 and name.json()["data"]["name"] == "记忆联调用户"
            created = client.post("/api/user/memories", headers=headers[0], json={
                "title": "表达偏好", "content": "喜欢简洁、短句的中文回答",
            })
            assert created.status_code == 200, created.text
            user_memory = created.json()["data"]
            assert user_memory["source"] == "user"
            profile = client.post("/api/user/memories", headers=headers[0], json={
                "title": "Deckwise personalization profile",
                "content": "Occupation: Python developer\n\nAbout:\n研究 Agent 技术",
            })
            assert profile.status_code == 200
            rule = client.post("/api/user/rules", headers=headers[0], json={
                "content": "User custom instructions:\n回答时用中文",
            })
            assert rule.status_code == 200
            rule_id = rule.json()["data"]["id"]
            assert "回答时用中文" in client.get("/api/user/rules", headers=headers[0]).text
            assert client.put(f"/api/user/rules/{rule_id}", headers=headers[0], json={
                "content": "User custom instructions:\n用中文简洁回答",
            }).json()["data"] is True
            assert client.get("/api/user/memories", headers=headers[1]).json()["data"] == []
            assert client.put(f"/api/user/memories/{user_memory['id']}", headers=headers[1], json={
                "title": "越权", "content": "应拒绝",
            }).status_code == 404
            assert client.delete(f"/api/user/memories/{user_memory['id']}", headers=headers[1]).status_code == 404
            assert client.put(f"/api/user/rules/{rule_id}/toggle?enabled=false", headers=headers[1]).status_code == 404
            agent = make_manage_user_memory_tool(user_ids[0])
            added = agent.invoke({"action": "create", "title": "技术背景", "content": "长期学习 Python 和 LangGraph，喜欢简洁说明"})
            import json
            agent_memory = json.loads(added)
            assert agent_memory["success"] and agent_memory["source"] == "ai"
            for index in range(3):
                distractor = client.post("/api/user/memories", headers=headers[0], json={
                    "title": f"临时项目 {index}", "content": "记录 FastAPI 服务部署和 PostgreSQL 配置",
                })
                assert distractor.status_code == 200
            first = asyncio.run(memory_retrieval_service.relevant_context(user_ids[0], "如何回答得更简洁？"),
                                loop_factory=selector_loop_factory)
            assert "用户画像" in first and "表达偏好" in first
            assert len(asyncio.run(indexed_keys(user_ids[0]), loop_factory=selector_loop_factory)) == 5
            second = asyncio.run(memory_retrieval_service.relevant_context(user_ids[0], "我喜欢哪种简洁说明？"),
                                 loop_factory=selector_loop_factory)
            assert "技术背景" in second
            assert asyncio.run(memory_retrieval_service.relevant_context(user_ids[1], "我偏好什么？"),
                               loop_factory=selector_loop_factory) == ""
            changed = client.put(f"/api/user/memories/{user_memory['id']}", headers=headers[0], json={
                "title": "表达偏好", "content": "喜欢简洁、有标题的回答",
            })
            assert changed.status_code == 200 and changed.json()["data"] is True
            current = asyncio.run(memory_retrieval_service.relevant_context(user_ids[0], "如何回答得更简洁？"),
                                  loop_factory=selector_loop_factory)
            assert "有标题" in current and "短句" not in current
            assert client.delete(f"/api/user/memories/{user_memory['id']}", headers=headers[0]).status_code == 200
            removed = asyncio.run(memory_retrieval_service.relevant_context(user_ids[0], "如何回答得更简洁？"),
                                  loop_factory=selector_loop_factory)
            assert "表达偏好" not in removed
            assert len(asyncio.run(indexed_keys(user_ids[0]), loop_factory=selector_loop_factory)) == 4
            assert client.put(f"/api/user/rules/{rule_id}/toggle?enabled=false", headers=headers[0]).status_code == 200
            from app.services.user_rule_service import enabled_rules_context
            assert enabled_rules_context(user_ids[0]) == ""
            assert client.delete(f"/api/user/rules/{rule_id}", headers=headers[0]).json()["data"] is True
        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        if base_url:
            with httpx.Client(base_url=base_url, cookies={COOKIE_NAME: tokens[0]},
                              timeout=15, trust_env=False) as web:
                assert web.get("/api/user/memories").status_code == 200
                assert web.get("/api/user/rules").status_code == 200
                created_web = web.post("/api/user/memories", json={
                    "title": "Web 代理检查", "content": "用户可通过同源代理管理长期记忆",
                })
                assert created_web.status_code == 200, created_web.text
                assert web.delete(f"/api/user/memories/{created_web.json()['data']['id']}").status_code == 200
        print("memory flow OK: user/Agent writes, semantic recall, updates, deletion, rules, isolation")
    finally:
        embedding_service.openrouter_bge_embeddings = original_embeddings
        model_credential_service.configured_providers = original_providers
        asyncio.run(clear_store(user_ids), loop_factory=selector_loop_factory)
        for token in tokens:
            auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as db:
            db.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
