"""Java-compatible AES-256-GCM envelope for user model credentials."""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import setting
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

KEY_VERSION = 1
NONCE_BYTES = 12


def _key() -> bytes:
    encoded = (setting("APP_MODEL_CREDENTIAL_ENCRYPTION_KEY") or "").strip()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raw = b""
    if len(raw) != 32:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "模型密钥加密配置不可用")
    return raw


def _aad(user_id: int, provider_id: str, version: int) -> bytes:
    return f"model-credential:v{version}:{user_id}:{provider_id}".encode("utf-8")


def encrypt(user_id: int, provider_id: str, api_key: str) -> tuple[bytes, bytes, int]:
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(_key()).encrypt(nonce, api_key.encode("utf-8"),
                                         _aad(user_id, provider_id, KEY_VERSION))
    return ciphertext, nonce, KEY_VERSION


def decrypt(user_id: int, provider_id: str, ciphertext: bytes, nonce: bytes, key_version: int) -> str:
    if key_version != KEY_VERSION or len(nonce) != NONCE_BYTES:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "模型密钥格式不可用")
    try:
        return AESGCM(_key()).decrypt(nonce, ciphertext, _aad(user_id, provider_id, key_version)).decode("utf-8")
    except (InvalidTag, UnicodeError, ValueError) as error:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "模型密钥解密失败") from error
