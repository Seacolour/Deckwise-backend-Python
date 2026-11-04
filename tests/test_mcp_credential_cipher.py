"""Notion MCP credentials are encrypted and bound to one user."""

import base64

import pytest

from app.core import mcp_credential_cipher
from app.core.exceptions import BusinessError


def test_roundtrip_and_user_binding(monkeypatch) -> None:
    monkeypatch.setattr(mcp_credential_cipher, "setting",
                        lambda _name: base64.b64encode(b"z" * 32).decode())
    value = {"client_id": "demo-client", "access_token": "demo-token"}
    ciphertext, nonce, version = mcp_credential_cipher.encrypt(7, "notion", value)
    assert b"demo-token" not in ciphertext
    assert mcp_credential_cipher.decrypt(7, "notion", ciphertext, nonce, version) == value
    with pytest.raises(BusinessError):
        mcp_credential_cipher.decrypt(8, "notion", ciphertext, nonce, version)


def test_missing_key_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(mcp_credential_cipher, "setting", lambda _name: "")
    with pytest.raises(BusinessError):
        mcp_credential_cipher.encrypt(7, "notion", {"access_token": "demo"})
