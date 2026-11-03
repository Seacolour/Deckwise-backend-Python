"""Exercise the Web workspace contract against local PostgreSQL and Redis."""

import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402


def _request(client: httpx.Client, method: str, path: str, token: str, **kwargs):
    return client.request(method, path, headers={"cookie": f"{COOKIE_NAME}={token}"}, **kwargs)


def main() -> None:
    suffix = secrets.token_hex(8)
    emails = [f"workspace-{suffix}-a@example.test", f"workspace-{suffix}-b@example.test"]
    tokens = [new_session_token(), new_session_token()]
    user_ids: list[int] = []

    try:
        with get_engine().begin() as connection:
            for email in emails:
                user_ids.append(connection.scalar(text("""
                    INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
                    VALUES (:email, true, 'email') RETURNING id
                """), {"email": email}))
        for token, user_id in zip(tokens, user_ids):
            auth_redis_repository.create_web_session(token, user_id)

        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        client_context = (httpx.Client(base_url=base_url, timeout=15) if base_url else
                          TestClient(app, backend_options={"loop_factory": selector_loop_factory}))
        with client_context as client:
            first, second = tokens
            list_body = {"current": 1, "pageSize": 100, "sortField": "updatedAt", "sortOrder": "desc", "archived": False}
            empty = _request(client, "POST", "/api/projects/list", first, json=list_body)
            assert empty.status_code == 200 and empty.json()["data"]["records"] == [], empty.text

            created = _request(client, "POST", "/api/projects/create", first,
                               json={"name": "测试工作区", "description": "阶段 1 联调"})
            assert created.status_code == 200, created.text
            project_id = created.json()["data"]["id"]
            assert created.json()["data"]["ownerId"] == str(user_ids[0])

            projects = _request(client, "POST", "/api/projects/list", first, json=list_body)
            assert projects.status_code == 200 and projects.json()["data"]["total"] == 1, projects.text
            assert projects.json()["data"]["pageSize"] == 100
            assert projects.json()["data"]["records"][0]["id"] == project_id
            assert _request(client, "POST", "/api/projects/list", second, json=list_body).json()["data"]["total"] == 0

            sessions = _request(client, "POST", f"/api/projects/{project_id}/list", first,
                                json={"current": 1, "pageSize": 100, "sortField": "lastActiveAt", "sortOrder": "desc"})
            assert sessions.status_code == 200 and sessions.json()["data"]["records"] == [], sessions.text
            with get_engine().begin() as connection:
                session_id = connection.scalar(text("""
                    INSERT INTO backend_data.sessions (project_id, created_by, title)
                    VALUES (:project_id, :user_id, '测试对话') RETURNING id
                """), {"project_id": int(project_id), "user_id": user_ids[0]})
            sessions = _request(client, "POST", f"/api/projects/{project_id}/list", first,
                                json={"current": 1, "pageSize": 100, "sortField": "lastActiveAt", "sortOrder": "desc"})
            assert sessions.json()["data"]["records"][0]["id"] == str(session_id), sessions.text
            assert sessions.json()["data"]["total"] == 1
            files = _request(client, "GET", f"/api/projects/{project_id}/files", first)
            assert files.status_code == 200 and files.json()["data"] == [], files.text

            cache_key = secrets.token_hex(32)
            with get_engine().begin() as connection:
                file_id = connection.scalar(text("""
                    INSERT INTO backend_data.object_storage_files
                        (owner_user_id, source_key, bucket, object_key, original_name)
                    VALUES (:user_id, :cache_key, 'test-bucket', :object_key, 'source.txt')
                    RETURNING id
                """), {"user_id": user_ids[0], "cache_key": cache_key,
                       "object_key": f"workspace-test/{suffix}.txt"})
                connection.execute(text("""
                    INSERT INTO backend_data.project_file_links
                        (project_id, file_id, added_by, display_name)
                    VALUES (:project_id, :file_id, :user_id, 'linked.txt')
                """), {"project_id": int(project_id), "file_id": file_id, "user_id": user_ids[0]})
            linked_files = _request(client, "GET", f"/api/projects/{project_id}/files", first)
            assert linked_files.status_code == 200, linked_files.text
            assert linked_files.json()["data"][0]["id"] == str(file_id)
            assert linked_files.json()["data"][0]["cacheKey"] == cache_key
            assert linked_files.json()["data"][0]["fileName"] == "linked.txt"

            document = _request(client, "POST", "/api/documents/create", first,
                                json={"projectId": project_id, "title": "测试文档", "draftContent": "# 初稿\n"})
            assert document.status_code == 200, document.text
            document_id = document.json()["data"]["id"]
            assert document.json()["data"]["documentType"] == "MARKDOWN"
            assert document.json()["data"]["version"] == 1

            listed = _request(client, "GET", "/api/documents/list", first, params={"projectId": project_id, "limit": 100})
            assert listed.status_code == 200 and listed.json()["data"][0]["id"] == document_id, listed.text
            detail = _request(client, "GET", f"/api/documents/{document_id}", first)
            assert detail.status_code == 200 and detail.json()["data"]["draftContent"] == "# 初稿\n", detail.text

            saved = _request(client, "PUT", f"/api/documents/{document_id}/draft", first,
                             json={"version": 1, "draftContent": "# 第二稿\n"})
            assert saved.status_code == 200 and saved.json()["data"]["version"] == 2, saved.text
            stale = _request(client, "PUT", f"/api/documents/{document_id}/draft", first,
                             json={"version": 1, "draftContent": "旧内容"})
            assert stale.status_code == 409 and stale.json()["code"] == 40903, stale.text
            reread = _request(client, "GET", f"/api/documents/{document_id}", first)
            assert reread.json()["data"]["draftContent"] == "# 第二稿\n"
            assert reread.json()["data"]["version"] == 2

            assert _request(client, "GET", f"/api/documents/{document_id}", second).status_code == 404
            assert _request(client, "PUT", f"/api/documents/{document_id}/draft", second,
                            json={"version": 2, "draftContent": "越权"}).status_code == 404
            assert _request(client, "GET", "/api/documents/list", second,
                            params={"projectId": project_id}).status_code == 404
            assert _request(client, "GET", f"/api/projects/{project_id}/files", second).status_code == 404
            assert _request(client, "POST", f"/api/projects/{project_id}/list", second,
                            json={"current": 1, "pageSize": 10}).status_code == 404
            assert _request(client, "POST", "/api/projects/list", first,
                            json={**list_body, "sortField": "unsafe"}).status_code == 400

        print("workspace flow OK: project, session/file lists, document create/read/save, version conflict, ownership")
    finally:
        for token in tokens:
            auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
