"""Catalog and BYOK jointly determine each user's callable models."""

import pytest
from langchain_openai import ChatOpenAI

from app.core.exceptions import BusinessError
from app.services import model_catalog, model_credential_service, model_service


def test_models_are_scoped_to_user_credentials(monkeypatch) -> None:
    configured = {7: {"deepseek"}, 8: {"openrouter"}, 9: set()}
    monkeypatch.setattr(model_credential_service, "configured_providers",
                        lambda user_id: configured[user_id])
    monkeypatch.setattr(model_credential_service, "resolve_api_key",
                        lambda user_id, provider_id: "test-only-key" if provider_id in configured[user_id] else None)

    assert [item.id for item in model_service.available_models(7)] == ["deepseek-chat"]
    assert [item.id for item in model_service.available_models(8)] == ["openai/gpt-6-luna"]
    assert model_service.available_models(9) == []
    assert model_service.supports_images(7, "openai/gpt-6-luna") is False
    assert model_service.supports_images(8, "openai/gpt-6-luna") is True
    assert model_service.supports_images(8, "deepseek-chat") is False

    model = model_service.resolve_chat_model(8, "openai/gpt-6-luna")
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "openai/gpt-6-luna"
    assert str(model.openai_api_base).rstrip("/") == "https://openrouter.ai/api/v1"
    with pytest.raises(BusinessError, match="账户设置"):
        model_service.resolve_chat_model(9, "deepseek-chat")


def test_catalog_contains_only_enabled_supported_models() -> None:
    catalog = model_catalog.load_catalog()
    assert catalog.defaultModel == "deepseek-chat"
    assert all(item.apiFormat == "chat-completions" for item in catalog.models)
    assert model_catalog.find_enabled_model("made-up-model") is None


def test_catalog_flags_control_mode_and_enabled_state(monkeypatch) -> None:
    catalog = model_catalog.ModelCatalog.model_validate({
        "defaultModel": "agent-only",
        "models": [
            {"id": "agent-only", "providerId": "deepseek", "upstreamModelId": "deepseek-chat",
             "apiFormat": "chat-completions", "displayName": "Agent only",
             "askSupported": False, "agentSupported": True, "imageSupported": False},
            {"id": "hidden", "providerId": "deepseek", "upstreamModelId": "deepseek-chat",
             "apiFormat": "chat-completions", "displayName": "Hidden",
             "askSupported": True, "agentSupported": True, "enabled": False},
        ],
    })
    monkeypatch.setattr(model_catalog, "load_catalog", lambda: catalog)
    monkeypatch.setattr(model_credential_service, "configured_providers", lambda _user_id: {"deepseek"})
    monkeypatch.setattr(model_credential_service, "resolve_api_key", lambda _user_id, _provider_id: "test-only-key")
    assert [item.id for item in model_service.available_models(7)] == ["agent-only"]
    with pytest.raises(BusinessError, match="对话模式"):
        model_service.resolve_chat_model(7, "agent-only", "ASK")
    with pytest.raises(BusinessError, match="模型不可用"):
        model_service.resolve_chat_model(7, "hidden", "AGENT")
