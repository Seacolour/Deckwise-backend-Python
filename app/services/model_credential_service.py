"""Validate, encrypt, and resolve each user's provider credentials."""

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.core.model_credential_cipher import decrypt, encrypt
from app.db.session import session_scope
from app.repositories import model_credential_repository
from app.schemas.model_credential import ModelCredentialStatus

PROVIDER_IDS = ("deepseek", "openrouter")
MAX_API_KEY_CHARS = 4096


def _provider(provider_id: str) -> None:
    if provider_id not in PROVIDER_IDS:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "不支持的模型提供商")


def configured_providers(user_id: int) -> set[str]:
    with session_scope() as db:
        return model_credential_repository.list_providers(db, user_id)


def list_status(user_id: int) -> list[ModelCredentialStatus]:
    with session_scope() as db:
        suffixes = model_credential_repository.list_suffixes(db, user_id)
    return [ModelCredentialStatus(
        providerId=provider_id, configured=provider_id in suffixes,
        maskedKey="****" + suffixes[provider_id] if provider_id in suffixes else None,
    ) for provider_id in PROVIDER_IDS]


def normalize_api_key(api_key: str) -> str:
    if not api_key or not api_key.strip() or len(api_key) > MAX_API_KEY_CHARS or any(
        ord(char) < 32 or ord(char) == 127 for char in api_key
    ):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "无效的模型 API Key")
    return api_key.strip()


def upsert(user_id: int, provider_id: str, api_key: str) -> ModelCredentialStatus:
    _provider(provider_id)
    normalized = normalize_api_key(api_key)
    ciphertext, nonce, version = encrypt(user_id, provider_id, normalized)
    suffix = normalized[-4:]
    with session_scope() as db:
        model_credential_repository.upsert(db, user_id, provider_id, ciphertext, nonce, version, suffix)
    return ModelCredentialStatus(providerId=provider_id, configured=True, maskedKey="****" + suffix)


def delete(user_id: int, provider_id: str) -> bool:
    _provider(provider_id)
    with session_scope() as db:
        return model_credential_repository.delete(db, user_id, provider_id)


def resolve_api_key(user_id: int, provider_id: str) -> str | None:
    _provider(provider_id)
    with session_scope() as db:
        stored = model_credential_repository.find(db, user_id, provider_id)
    if stored is None:
        return None
    return decrypt(user_id, provider_id, stored["ciphertext"], stored["nonce"], stored["key_version"])
