"""Encrypted per-user API keys in the existing Flyway V11/V12 table."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_providers(db: Session, user_id: int) -> set[str]:
    return set(db.scalars(text("""
        SELECT provider_id FROM backend_data.user_model_credentials WHERE user_id = :user_id
    """), {"user_id": user_id}).all())


def list_suffixes(db: Session, user_id: int) -> dict[str, str]:
    rows = db.execute(text("""
        SELECT provider_id, key_suffix FROM backend_data.user_model_credentials
        WHERE user_id = :user_id
    """), {"user_id": user_id}).mappings().all()
    return {row["provider_id"]: row["key_suffix"] for row in rows}


def find(db: Session, user_id: int, provider_id: str) -> dict | None:
    row = db.execute(text("""
        SELECT ciphertext, nonce, key_version FROM backend_data.user_model_credentials
        WHERE user_id = :user_id AND provider_id = :provider_id
    """), {"user_id": user_id, "provider_id": provider_id}).mappings().one_or_none()
    return dict(row) if row else None


def upsert(db: Session, user_id: int, provider_id: str, ciphertext: bytes,
           nonce: bytes, key_version: int, suffix: str) -> None:
    db.execute(text("""
        INSERT INTO backend_data.user_model_credentials
            (user_id, provider_id, ciphertext, nonce, key_version, key_suffix)
        VALUES (:user_id, :provider_id, :ciphertext, :nonce, :key_version, :suffix)
        ON CONFLICT (user_id, provider_id) DO UPDATE SET
            ciphertext = EXCLUDED.ciphertext,
            nonce = EXCLUDED.nonce,
            key_version = EXCLUDED.key_version,
            key_suffix = EXCLUDED.key_suffix
    """), {"user_id": user_id, "provider_id": provider_id,
           "ciphertext": ciphertext, "nonce": nonce, "key_version": key_version,
           "suffix": suffix})


def delete(db: Session, user_id: int, provider_id: str) -> bool:
    row = db.scalar(text("""
        DELETE FROM backend_data.user_model_credentials
        WHERE user_id = :user_id AND provider_id = :provider_id
        RETURNING provider_id
    """), {"user_id": user_id, "provider_id": provider_id})
    return row is not None
