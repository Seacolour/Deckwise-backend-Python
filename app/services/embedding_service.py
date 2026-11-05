"""Shared user BYOK embeddings for project RAG and semantic memories."""

from langchain_openai import OpenAIEmbeddings

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.services import model_credential_service

EMBEDDING_MODEL = "baai/bge-m3"
EMBEDDING_DIMENSIONS = 1024


def openrouter_bge_embeddings(user_id: int) -> OpenAIEmbeddings:
    key = model_credential_service.resolve_api_key(user_id, "openrouter")
    if not key:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR,
                            "语义检索需要先在账户设置中配置 OpenRouter API Key")
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL, base_url="https://openrouter.ai/api/v1",
        api_key=key, check_embedding_ctx_length=False,
        chunk_size=16, timeout=30, max_retries=1,
    )
