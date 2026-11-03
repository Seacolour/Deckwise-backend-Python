"""Per-user API keys are encrypted and authenticated by user and provider."""

import base64

import pytest

from app.core import model_credential_cipher
from app.core.exceptions import BusinessError


def test_credential_cipher_roundtrip_and_aad_binding(monkeypatch) -> None:
    monkeypatch.setattr(model_credential_cipher, "setting",
                        lambda _name: base64.b64encode(b"x" * 32).decode())
    ciphertext, nonce, version = model_credential_cipher.encrypt(7, "deepseek", "local-test-key")
    assert b"local-test-key" not in ciphertext
    assert len(nonce) == 12 and version == 1
    assert model_credential_cipher.decrypt(7, "deepseek", ciphertext, nonce, version) == "local-test-key"
    with pytest.raises(BusinessError):
        model_credential_cipher.decrypt(8, "deepseek", ciphertext, nonce, version)
    with pytest.raises(BusinessError):
        model_credential_cipher.decrypt(7, "openrouter", ciphertext, nonce, version)


def test_missing_encryption_key_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(model_credential_cipher, "setting", lambda _name: "")
    with pytest.raises(BusinessError) as error:
        model_credential_cipher.encrypt(7, "deepseek", "local-test-key")
    assert error.value.status == 503
