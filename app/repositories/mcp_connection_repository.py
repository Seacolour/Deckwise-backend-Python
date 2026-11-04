"""Persist encrypted user-bound MCP OAuth connections."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def find(db: Session, user_id: int, provider_id: str = "notion", *, lock: bool = False) -> dict | None:
    statement = """
        SELECT status, credential_ciphertext, nonce, key_version, workspace_id, workspace_name, updated_at
        FROM backend_data.user_mcp_connections
        WHERE user_id = :user_id AND provider_id = :provider_id
    """ + (" FOR UPDATE" if lock else "")
    row = db.execute(text(statement), {"user_id": user_id, "provider_id": provider_id}).mappings().one_or_none()
    return dict(row) if row else None


def upsert(db: Session, user_id: int, provider_id: str, status: str,
           ciphertext: bytes, nonce: bytes, key_version: int,
           workspace_id: str | None = None, workspace_name: str | None = None) -> None:
    db.execute(text("""
        INSERT INTO backend_data.user_mcp_connections
            (user_id, provider_id, status, credential_ciphertext, nonce, key_version,
             workspace_id, workspace_name)
        VALUES (:user_id, :provider_id, :status, :ciphertext, :nonce, :key_version,
                :workspace_id, :workspace_name)
        ON CONFLICT (user_id, provider_id) DO UPDATE SET
            status = EXCLUDED.status,
            credential_ciphertext = EXCLUDED.credential_ciphertext,
            nonce = EXCLUDED.nonce,
            key_version = EXCLUDED.key_version,
            workspace_id = EXCLUDED.workspace_id,
            workspace_name = EXCLUDED.workspace_name
    """), {"user_id": user_id, "provider_id": provider_id, "status": status,
           "ciphertext": ciphertext, "nonce": nonce, "key_version": key_version,
           "workspace_id": workspace_id, "workspace_name": workspace_name})


def set_status(db: Session, user_id: int, provider_id: str, status: str) -> None:
    db.execute(text("""
        UPDATE backend_data.user_mcp_connections SET status = :status
        WHERE user_id = :user_id AND provider_id = :provider_id
    """), {"user_id": user_id, "provider_id": provider_id, "status": status})


def delete(db: Session, user_id: int, provider_id: str = "notion") -> bool:
    row = db.scalar(text("""
        DELETE FROM backend_data.user_mcp_connections
        WHERE user_id = :user_id AND provider_id = :provider_id
        RETURNING provider_id
    """), {"user_id": user_id, "provider_id": provider_id})
    return row is not None
