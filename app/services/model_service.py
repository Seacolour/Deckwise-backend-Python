"""Catalog models become callable only with the current user's BYOK credential."""

from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.schemas.model import AvailableModelDTO
from app.services import model_catalog, model_credential_service
from app.services.model_catalog import ModelDefinition


def available_models(user_id: int) -> list[AvailableModelDTO]:
    providers = model_credential_service.configured_providers(user_id)
    return [AvailableModelDTO(
        id=model.id, providerId=model.providerId, displayName=model.displayName,
        description=model.description, requiredCapability="VISION" if model.imageSupported else None,
        askSupported=model.askSupported, agentSupported=model.agentSupported,
        imageSupported=model.imageSupported,
    ) for model in model_catalog.load_catalog().models
        if model.enabled and model.providerId in providers]


def supports_images(user_id: int, model_id: str) -> bool:
    model = model_catalog.find_enabled_model(model_id)
    return bool(model and model.imageSupported
                and model.providerId in model_credential_service.configured_providers(user_id))


def build_chat_model(model: ModelDefinition, key: str, *, timeout: int = 60,
                     max_tokens: int = 2048, max_retries: int = 1) -> BaseChatModel:
    if model.providerId == "openrouter":
        return ChatOpenAI(
            model=model.upstreamModelId, api_key=key, base_url="https://openrouter.ai/api/v1",
            timeout=timeout, max_retries=max_retries, max_tokens=max_tokens,
        )
    return ChatDeepSeek(model=model.upstreamModelId, api_key=key,
                        timeout=timeout, max_retries=max_retries, max_tokens=max_tokens)


def resolve_chat_model(user_id: int, model_id: str, mode: str = "ASK") -> BaseChatModel:
    model = model_catalog.find_enabled_model(model_id)
    if model is None:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "模型不可用")
    if (mode == "ASK" and not model.askSupported) or (mode == "AGENT" and not model.agentSupported):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "该模型不支持当前对话模式")
    key = model_credential_service.resolve_api_key(user_id, model.providerId)
    if not key:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR,
                            f"请先在账户设置中配置 {model.providerId} API Key")
    return build_chat_model(model, key)
