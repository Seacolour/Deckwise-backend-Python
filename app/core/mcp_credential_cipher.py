"""Encrypt per-user MCP OAuth data using a domain-separated project key."""

import base64
import binascii
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import setting
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

KEY_VERSION = 1


def _key() -> bytes:
    encoded = (setting("APP_MODEL_CREDENTIAL_ENCRYPTION_KEY") or "").strip()
    try:
        master = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        master = b""
    if len(master) != 32:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "MCP 凭据加密配置不可用")
    return HKDF(algorithm=SHA256(), length=32, salt=None,
                info=b"deckwise:notion-mcp-credential:v1").derive(master)


def _aad(user_id: int, provider_id: str) -> bytes:
    return f"mcp-credential:v{KEY_VERSION}:{user_id}:{provider_id}".encode()


def encrypt(user_id: int, provider_id: str, value: dict) -> tuple[bytes, bytes, int]:
    nonce = os.urandom(12)
    plaintext = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    return AESGCM(_key()).encrypt(nonce, plaintext, _aad(user_id, provider_id)), nonce, KEY_VERSION


def decrypt(user_id: int, provider_id: str, ciphertext: bytes,
            nonce: bytes, key_version: int) -> dict:
    if key_version != KEY_VERSION or len(nonce) != 12:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "MCP 凭据格式不可用")
    try:
        plaintext = AESGCM(_key()).decrypt(nonce, ciphertext, _aad(user_id, provider_id))
        result = json.loads(plaintext)
        if not isinstance(result, dict):
            raise ValueError("invalid credential object")
        return result
    except (InvalidTag, UnicodeError, ValueError, TypeError) as error:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "MCP 凭据解密失败") from error
