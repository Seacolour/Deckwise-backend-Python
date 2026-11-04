"""Persist per-user switches for approved Agent plugins."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_overrides(db: Session, user_id: int) -> dict[str, bool]:
    rows = db.execute(text("""
        SELECT plugin_id, enabled FROM backend_data.user_agent_plugin_settings
        WHERE user_id = :user_id
    """), {"user_id": user_id}).mappings().all()
    return {row["plugin_id"]: row["enabled"] for row in rows}


def set_enabled(db: Session, user_id: int, plugin_id: str, enabled: bool) -> None:
    db.execute(text("""
        INSERT INTO backend_data.user_agent_plugin_settings (user_id, plugin_id, enabled)
        VALUES (:user_id, :plugin_id, :enabled)
        ON CONFLICT (user_id, plugin_id) DO UPDATE SET enabled = EXCLUDED.enabled
    """), {"user_id": user_id, "plugin_id": plugin_id, "enabled": enabled})
