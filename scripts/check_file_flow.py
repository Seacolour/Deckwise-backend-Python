"""Upload synthetic TXT/PDF/DOCX files to private R2 and verify parsed Agent reads."""

import os
import secrets
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pypandoc
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from reportlab.pdfgen import canvas
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.r2_storage import delete_private_object, private_settings  # noqa: E402
from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services import file_service, model_service  # noqa: E402
from app.core.exceptions import BusinessError  # noqa: E402


class ScriptedFileModel:
    def __init__(self, cache_key: str):
        self.cache_key = cache_key

    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        if any(isinstance(message, ToolMessage) for message in messages):
            return AIMessage(content="已按分片读取所附文件。")
        return AIMessage(content="", tool_calls=[{
            "name": "file_content_read",
            "args": {"cache_key": self.cache_key, "start_index": 0, "limit": 2},
            "id": "file-read-1",
        }])


def synthetic_pdf() -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(72, 750, "First PDF page for Deckwise")
    pdf.showPage()
    pdf.drawString(72, 750, "Second PDF page for Deckwise")
    pdf.save()
    return output.getvalue()


def synthetic_docx() -> bytes:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "source.docx"
        pypandoc.convert_text("# Pandoc heading\n\nThis is a Word document.",
                              to="docx", format="md", outputfile=str(path))
        return path.read_bytes()


def main() -> None:
    email = f"file-check-{secrets.token_hex(8)}@example.test"
    other_email = f"file-check-{secrets.token_hex(8)}-other@example.test"
    token = new_session_token()
    other_token = new_session_token()
    with get_engine().begin() as db:
        user_id = db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email})
        other_user_id = db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": other_email})
    auth_redis_repository.create_web_session(token, user_id)
    auth_redis_repository.create_web_session(other_token, other_user_id)
    headers = {"cookie": f"{COOKIE_NAME}={token}"}
    original_model_resolver = model_service.resolve_chat_model

    try:
        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        client_context = (httpx.Client(base_url=base_url, timeout=120) if base_url else
                          TestClient(app, backend_options={"loop_factory": selector_loop_factory}))
        with client_context as client:
            project = client.post("/api/projects/create", headers=headers, json={"name": "文件解析联调"})
            assert project.status_code == 200, project.text
            project_id = project.json()["data"]["id"]
            text_body = "\n".join(f"Segment {index}: context pressure sample text." for index in range(250)).encode()
            files = [
                ("files", ("long.txt", text_body, "text/plain")),
                ("files", ("sample.pdf", synthetic_pdf(), "application/pdf")),
                ("files", ("sample.docx", synthetic_docx(),
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ]
            uploaded = client.post(
                "/api/files/upload/batch", headers=headers,
                params={"projectId": project_id, "uploadSource": "user_upload"},
                files=files,
            )
            assert uploaded.status_code == 200, uploaded.text[:900]
            data = uploaded.json()["data"]
            assert data["totalCount"] == 3 and len(data["files"]) == 3
            assert all(item["totalFragments"] > 0 and len(item["cacheKey"]) == 64 for item in data["files"])
            assert data["files"][0]["totalFragments"] > 1
            repeated = client.post(
                "/api/files/upload/batch", headers=headers,
                params={"projectId": project_id, "uploadSource": "user_upload"},
                files=[("files", ("long.txt", text_body, "text/plain"))],
            )
            assert repeated.status_code == 200 and repeated.json()["data"]["files"][0]["sourceFileId"] == data["files"][0]["sourceFileId"]

            listed = client.get(f"/api/projects/{project_id}/files", headers=headers)
            assert listed.status_code == 200 and len(listed.json()["data"]) == 3, listed.text
            text_file = data["files"][0]
            page = file_service.read_file_fragments(user_id, int(project_id), text_file["cacheKey"], 0, 2)
            assert len(page.fragments) == 2 and page.hasMore
            next_page = file_service.read_file_fragments(user_id, int(project_id), text_file["cacheKey"], 2, 2)
            assert next_page.fragments and next_page.fragments[0].index == 2

            preview = client.get(f"/api/files/{text_file['sourceFileId']}/access-url", headers=headers,
                                 params={"projectId": project_id})
            assert preview.status_code == 200, preview.text
            denied_preview = client.get(f"/api/files/{text_file['sourceFileId']}/access-url",
                                        headers={"cookie": f"{COOKIE_NAME}={other_token}"},
                                        params={"projectId": project_id})
            assert denied_preview.status_code == 404
            try:
                file_service.read_file_fragments(other_user_id, int(project_id), text_file["cacheKey"], 0, 1)
                raise AssertionError("cross-user parsed text read succeeded")
            except BusinessError as error:
                assert error.status == 404
            fetched = httpx.get(preview.json()["data"]["accessUrl"], timeout=15)
            assert fetched.status_code == 200 and fetched.content == text_body

            session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                  json={"title": "文件读取"})
            session_id = session.json()["data"]["id"]
            if not base_url:
                model_service.resolve_chat_model = lambda _model_id: ScriptedFileModel(text_file["cacheKey"])
            stream_prefix = "/sse" if os.getenv("DECKWISE_CHECK_WEB_PROXY") == "1" else "/api"
            streamed = client.post(f"{stream_prefix}/sessions/{session_id}/sendRPC", headers=headers, json={
                "message": "读取我附加的文件。", "mode": "ASK", "model": "deepseek-chat",
                "fileCacheKeys": [text_file["cacheKey"]],
            })
            assert streamed.status_code == 200 and '"name":"file_content_read"' in streamed.text
            assert "event: done" in streamed.text
            history = client.get(f"/api/sessions/{session_id}/messages/after-seq", headers=headers)
            assert history.status_code == 200 and len(history.json()["data"]) >= 3

            print("file flow OK: TXT/PDF/DOCX upload, R2 preview, fragments, Agent read")
    finally:
        model_service.resolve_chat_model = original_model_resolver
        with get_engine().begin() as db:
            keys = db.execute(text("""
                SELECT object_key FROM backend_data.object_storage_files WHERE owner_user_id = :user_id
            """), {"user_id": user_id}).scalars().all()
        settings = private_settings()
        for object_key in keys:
            delete_private_object(settings, object_key)
        auth_redis_repository.revoke_web_session(token)
        auth_redis_repository.revoke_web_session(other_token)
        with get_engine().begin() as db:
            db.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"),
                       {"emails": [email, other_email]})


if __name__ == "__main__":
    main()
