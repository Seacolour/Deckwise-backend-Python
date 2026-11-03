"""Models callable through the Python conversation endpoint."""

from langchain_deepseek import ChatDeepSeek

from app.core.config import setting
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.schemas.model import AvailableModelDTO


def available_models() -> list[AvailableModelDTO]:
    if not (setting("DEEPSEEK_API_KEY") or "").strip():
        return []
    model_id = (setting("DECKWISE_DEEPSEEK_MODEL", "deepseek-chat") or "").strip()
    if not model_id:
        return []
    return [AvailableModelDTO(
        id=model_id,
        providerId="deepseek",
        displayName="DeepSeek Chat",
        description="DeepSeek 文档问答与编辑",
        askSupported=True,
        agentSupported=True,
    )]


def resolve_chat_model(model_id: str) -> ChatDeepSeek:
    available = next((item for item in available_models() if item.id == model_id), None)
    if available is None:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "模型不可用")
    key = (setting("DEEPSEEK_API_KEY") or "").strip()
    return ChatDeepSeek(model=model_id, api_key=key, timeout=60, max_retries=1, max_tokens=2048)
