"""Bounded memory context remains usable without semantic embeddings."""

import asyncio
from types import SimpleNamespace

from app.services import memory_retrieval_service


def test_recent_memory_fallback_and_profile_are_bounded(monkeypatch) -> None:
    memories = [SimpleNamespace(id="1", title="Deckwise personalization profile",
                                content="Occupation: writer\nAbout: concise answers", source="user")]
    memories.extend(SimpleNamespace(id=str(index), title=f"偏好 {index}",
                                    content="用户习惯", source="user") for index in range(2, 7))
    monkeypatch.setattr(memory_retrieval_service.user_memory_service, "list_memories",
                        lambda _user_id: memories)
    monkeypatch.setattr(memory_retrieval_service.model_credential_service, "configured_providers",
                        lambda _user_id: set())
    monkeypatch.setattr(memory_retrieval_service, "_semantic_hits",
                        lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected embedding")))

    context = asyncio.run(memory_retrieval_service.relevant_context(7, "我的习惯是什么？"))
    assert "用户画像" in context
    assert all(f"偏好 {index}" in context for index in (2, 3, 4))
    assert "偏好 5" not in context
    assert len(context) <= memory_retrieval_service.MAX_CONTEXT_CHARS
    assert memory_retrieval_service._namespace(7) != memory_retrieval_service._namespace(8)
