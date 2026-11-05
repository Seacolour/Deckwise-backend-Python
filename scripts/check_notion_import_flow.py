"""Real Notion MCP → private R2/project file snapshot check; removes test data."""

import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.r2_storage import delete_private_object, private_settings  # noqa: E402
from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402


def main() -> None:
    page = os.getenv("DECKWISE_TEST_NOTION_PAGE_ID", "").strip()
    if not page:
        raise SystemExit("Set DECKWISE_TEST_NOTION_PAGE_ID to a page you may import")
    with get_engine().connect() as db:
        user_id = db.scalar(text("""
            SELECT user_id FROM backend_data.user_mcp_connections
            WHERE provider_id = 'notion' AND status = 'connected'
            ORDER BY updated_at DESC LIMIT 1
        """))
    if user_id is None:
        raise SystemExit("Connect Notion in the Web plugin page first")
    marker = secrets.token_hex(8)
    other_email = f"notion-import-check-{marker}@example.test"
    with get_engine().begin() as db:
        other_user_id = db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": other_email})
        existing_ids = set(db.scalars(text("""
            SELECT id FROM backend_data.object_storage_files
            WHERE owner_user_id = :user_id AND source_type = 'notion'
        """), {"user_id": user_id}).all())
    token, other_token = new_session_token(), new_session_token()
    project_id = None
    new_file_ids: list[int] = []
    try:
        auth_redis_repository.create_web_session(token, user_id)
        auth_redis_repository.create_web_session(other_token, other_user_id)
        headers = {"cookie": f"{COOKIE_NAME}={token}"}
        other_headers = {"cookie": f"{COOKIE_NAME}={other_token}"}
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            project = client.post("/api/projects/create", headers=headers,
                                  json={"name": f"Notion 导入联调 {marker}"})
            assert project.status_code == 200, project.text
            project_id = int(project.json()["data"]["id"])
            body = {"projectId": project_id, "pageIdOrUrl": page}
            denied = client.post("/api/notion/pages/import", headers=other_headers, json=body)
            assert denied.status_code == 404, denied.text
            imported = client.post("/api/notion/pages/import", headers=headers, json=body)
            assert imported.status_code == 200, imported.text[:350]
            data = imported.json()["data"]
            file_id = int(data["file"]["sourceFileId"])
            if file_id not in existing_ids:
                new_file_ids.append(file_id)
            cache_key = data["file"]["cacheKey"]
            assert data["pageUrl"].startswith("https://")
            files = client.get(f"/api/projects/{project_id}/files", headers=headers)
            assert files.status_code == 200
            assert any(int(item["id"]) == file_id and item["sourceId"] == data["pageId"]
                       and item["sourceType"] == "notion"
                       for item in files.json()["data"])
            with get_engine().connect() as db:
                row = db.execute(text("""
                    SELECT source_type, source_id, object_key, metadata
                    FROM backend_data.object_storage_files WHERE id = :id
                """), {"id": file_id}).mappings().one()
                fragments = db.scalar(text("""
                    SELECT count(*) FROM backend_data.file_text_fragments
                    WHERE file_id = :id AND is_deleted = false
                """), {"id": file_id})
            assert row["source_type"] == "notion" and row["source_id"] == data["pageId"]
            assert row["metadata"]["source_url"] == data["pageUrl"] and fragments > 0
            repeat = client.post("/api/notion/pages/import", headers=headers, json=body)
            assert repeat.status_code == 200 and repeat.json()["data"]["file"]["sourceFileId"] == str(file_id)
            print("Notion import OK: owned page snapshot, private project file, fragments, dedup, isolation")
    finally:
        auth_redis_repository.revoke_web_session(token)
        auth_redis_repository.revoke_web_session(other_token)
        if project_id is not None:
            with get_engine().begin() as db:
                db.execute(text("DELETE FROM backend_data.projects WHERE id = :id AND owner_id = :user_id"),
                           {"id": project_id, "user_id": user_id})
        with get_engine().begin() as db:
            rows = db.execute(text("""
                DELETE FROM backend_data.object_storage_files AS f
                WHERE f.owner_user_id = :user_id AND f.source_type = 'notion'
                  AND f.id = ANY(:new_file_ids) AND NOT EXISTS (
                    SELECT 1 FROM backend_data.project_file_links AS l
                    WHERE l.file_id = f.id AND l.is_deleted = false
                  )
                RETURNING f.object_key
            """), {"user_id": user_id, "new_file_ids": new_file_ids}).scalars().all()
            db.execute(text("DELETE FROM backend_data.users WHERE id = :id"), {"id": other_user_id})
        settings = private_settings()
        for key in rows:
            delete_private_object(settings, key)


if __name__ == "__main__":
    main()
