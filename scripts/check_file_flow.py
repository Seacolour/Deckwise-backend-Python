"""Upload synthetic text, JSON, and image files to private R2 and verify Agent reads."""

import json
import os
import secrets
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pypandoc
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from PIL import Image
from reportlab.pdfgen import canvas
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.r2_storage import delete_private_object, private_settings  # noqa: E402
from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.core.config import setting  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services import file_service, model_service  # noqa: E402
from app.core.exceptions import BusinessError  # noqa: E402
from app.agent.tools import tools_for_project  # noqa: E402


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


class ScriptedSynthesisModel:
    """Exercise file read, document creation, local edit, and commit in one graph turn."""

    def __init__(self, cache_key: str):
        self.cache_key = cache_key

    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        results = [item for item in messages if isinstance(item, ToolMessage)]
        step = len(results)
        if step == 0:
            name, args = "file_content_read", {"cache_key": self.cache_key, "start_index": 0, "limit": 1}
        elif step == 1:
            page = json.loads(results[0].content)
            assert page["success"] and "Segment 0" in page["fragments"][0]["content"]
            name, args = "document_create", {"title": "资料整理", "content": "# 资料整理\nSegment 0\n待核验结论"}
        elif step == 2:
            created = json.loads(results[1].content)
            name, args = "document_locate", {"document_id": int(created["document_id"]), "query": "待核验结论"}
        elif step == 3:
            created = json.loads(results[1].content)
            found = json.loads(results[2].content)
            match = found["matches"][0]
            name, args = "document_diff", {"document_id": int(created["document_id"]), "hunks": [{
                "op": "REPLACE", "before": match["before"], "after": "已核验结论",
                "start_line": match["start_line"],
            }]}
        elif step == 4:
            created = json.loads(results[1].content)
            found = json.loads(results[2].content)
            assert json.loads(results[3].content)["must_call_document_save"]
            name, args = "document_save", {"document_id": int(created["document_id"]), "version": found["version"]}
        else:
            assert json.loads(results[4].content)["success"]
            return AIMessage(content="已根据文件创建并修改文档。")
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"synthesis-{step}",}])


class ScriptedJsonModel:
    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        results = [item for item in messages if isinstance(item, ToolMessage)]
        step = len(results)
        if step == 0:
            name, args = "file_list", {}
        else:
            listed = json.loads(results[0].content)
            item = next(item for item in listed["files"] if item["name"] == "config.json")
            assert "json_structure_read" in item["composite_tools"]
            file_id = int(item["file_id"])
            if step == 1:
                name, args = "json_structure_read", {"file_id": file_id, "path": "/settings", "max_depth": 3}
            elif step == 2:
                shape = json.loads(results[1].content)
                assert shape["success"] and shape["type"] == "object"
                name, args = "json_subtree_read", {"file_id": file_id, "path": "/settings/features/1"}
            else:
                leaf = json.loads(results[2].content)
                assert leaf["success"] and leaf["value"] == {"name": "beta", "enabled": False}
                return AIMessage(content="beta 功能未启用。")
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"json-{step}"}])


class ScriptedImageModel:
    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        current = next(item for item in reversed(messages) if isinstance(item, HumanMessage))
        assert isinstance(current.content, list)
        image = next(item for item in current.content if item.get("type") == "image_url")
        url = image["image_url"]["url"]
        response = httpx.get(url, timeout=15)
        assert response.status_code == 200 and response.content.startswith(b"\x89PNG\r\n\x1a\n")
        return AIMessage(content="图中是红色方块。")


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


def synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 64), "red").save(output, format="PNG")
    return output.getvalue()


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
    original_supports_images = model_service.supports_images

    try:
        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        client_context = (httpx.Client(base_url=base_url, timeout=120) if base_url else
                          TestClient(app, backend_options={"loop_factory": selector_loop_factory}))
        with client_context as client:
            if os.getenv("DECKWISE_REAL_JSON_MODEL") == "1":
                test_key = setting("DECKWISE_TEST_DEEPSEEK_API_KEY", aliases=("DEEPSEEK_API_KEY",))
                if not test_key:
                    raise SystemExit("Set DECKWISE_TEST_DEEPSEEK_API_KEY for a real-model test")
                provisioned = client.put("/api/user/model-credentials/deepseek", headers=headers,
                                         json={"apiKey": test_key})
                assert provisioned.status_code == 200, provisioned.text
            project = client.post("/api/projects/create", headers=headers, json={"name": "文件解析联调"})
            assert project.status_code == 200, project.text
            project_id = project.json()["data"]["id"]
            rejected_image_upload = client.post(
                "/api/files/upload/batch", headers=headers,
                params={"projectId": project_id, "uploadSource": "user_upload", "model": "deepseek-chat"},
                files=[("files", ("red.png", synthetic_png(), "image/png"))],
            )
            assert rejected_image_upload.status_code == 400 and "不支持图片上传" in rejected_image_upload.text
            model_service.supports_images = lambda _user_id, model_id: model_id == "openai/gpt-6-luna"
            text_body = "\n".join(f"Segment {index}: context pressure sample text." for index in range(250)).encode()
            files = [
                ("files", ("long.txt", text_body, "text/plain")),
                ("files", ("sample.pdf", synthetic_pdf(), "application/pdf")),
                ("files", ("sample.docx", synthetic_docx(),
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("files", ("config.json", json.dumps({
                    "settings": {"features": [{"name": "alpha", "enabled": True},
                                                {"name": "beta", "enabled": False}]},
                    "payload": "x" * 500,
                }).encode(), "application/json")),
                ("files", ("red.png", synthetic_png(), "image/png")),
            ]
            uploaded = client.post(
                "/api/files/upload/batch", headers=headers,
                params={"projectId": project_id, "uploadSource": "user_upload",
                        "model": "openai/gpt-6-luna"},
                files=files,
            )
            model_service.supports_images = original_supports_images
            assert uploaded.status_code == 200, uploaded.text[:900]
            data = uploaded.json()["data"]
            assert data["totalCount"] == 5 and len(data["files"]) == 5
            assert all(item["totalFragments"] > 0 and len(item["cacheKey"]) == 64 for item in data["files"][:4])
            assert data["files"][4]["totalFragments"] == 0
            assert data["files"][0]["totalFragments"] > 1
            repeated = client.post(
                "/api/files/upload/batch", headers=headers,
                params={"projectId": project_id, "uploadSource": "user_upload"},
                files=[("files", ("long.txt", text_body, "text/plain"))],
            )
            assert repeated.status_code == 200 and repeated.json()["data"]["files"][0]["sourceFileId"] == data["files"][0]["sourceFileId"]

            listed = client.get(f"/api/projects/{project_id}/files", headers=headers)
            assert listed.status_code == 200 and len(listed.json()["data"]) == 5, listed.text
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
                model_service.resolve_chat_model = lambda _user_id, _model_id, _mode: ScriptedFileModel(text_file["cacheKey"])
            stream_prefix = "/sse" if os.getenv("DECKWISE_CHECK_WEB_PROXY") == "1" else "/api"
            streamed = client.post(f"{stream_prefix}/sessions/{session_id}/sendRPC", headers=headers, json={
                "message": "读取我附加的文件。", "mode": "ASK", "model": "deepseek-chat",
                "fileCacheKeys": [text_file["cacheKey"]],
            })
            assert streamed.status_code == 200 and '"name":"file_content_read"' in streamed.text
            assert "event: done" in streamed.text
            history = client.get(f"/api/sessions/{session_id}/messages/after-seq", headers=headers)
            assert history.status_code == 200 and len(history.json()["data"]) >= 3
            first_user = next(item for item in history.json()["data"] if item["role"] == "user")
            assert first_user["attachments"][0]["name"] == "long.txt"
            assert first_user["attachments"][0]["fileId"] == text_file["sourceFileId"]

            if not base_url:
                model_service.resolve_chat_model = lambda _user_id, _model_id, _mode: ScriptedFileModel(data["files"][2]["cacheKey"])
                docx_turn = client.post(f"/api/sessions/{session_id}/sendRPC", headers=headers, json={
                    "message": "读取我附加的 DOCX。", "mode": "ASK", "model": "deepseek-chat",
                    "fileCacheKeys": [data["files"][2]["cacheKey"]],
                })
                assert docx_turn.status_code == 200 and "event: done" in docx_turn.text, docx_turn.text[-1000:]
                docx_history = client.get(f"/api/sessions/{session_id}/messages/after-seq", headers=headers)
                docx_user = [item for item in docx_history.json()["data"] if item["role"] == "user"][-1]
                assert docx_user["attachments"][0]["name"] == "sample.docx"

            if not base_url:
                model_service.resolve_chat_model = lambda _user_id, _model_id, _mode: ScriptedSynthesisModel(text_file["cacheKey"])
                synthesis_session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                                json={"title": "文件到文档"})
                assert synthesis_session.status_code == 200, synthesis_session.text
                synthesis_id = synthesis_session.json()["data"]["id"]
                synthesis = client.post(f"/api/sessions/{synthesis_id}/sendRPC", headers=headers, json={
                    "message": "根据所附文件创建文档并修正结论。", "mode": "AGENT", "model": "deepseek-chat",
                    "fileCacheKeys": [text_file["cacheKey"]],
                })
                assert synthesis.status_code == 200 and "event: done" in synthesis.text, synthesis.text[-1000:]
                events = [json.loads(line[6:]) for line in synthesis.text.splitlines()
                          if line.startswith("data: {")]
                tool_names = [event["name"] for event in events if event["type"] == "tool_call"]
                assert tool_names == ["file_content_read", "document_create", "document_locate",
                                      "document_diff", "document_save"], tool_names
                documents = client.get("/api/documents/list", headers=headers,
                                       params={"projectId": project_id})
                assert documents.status_code == 200, documents.text
                assert any("已核验结论" in (item.get("draftContent") or "")
                           for item in documents.json()["data"]), documents.text

                json_file_id = int(data["files"][3]["fileId"])
                json_tools = tools_for_project(user_id, int(project_id), "ASK")
                structure_tool = next(tool for tool in json_tools if tool.name == "json_structure_read")
                subtree_tool = next(tool for tool in json_tools if tool.name == "json_subtree_read")
                structure = json.loads(structure_tool.invoke({"file_id": json_file_id, "path": "/settings"}))
                assert structure["success"] and structure["type"] == "object", structure
                leaf = json.loads(subtree_tool.invoke({"file_id": json_file_id,
                                                      "path": "/settings/features/1"}))
                assert leaf["value"]["name"] == "beta", leaf
                invalid = json.loads(subtree_tool.invoke({"file_id": json_file_id, "path": "/missing"}))
                assert invalid["success"] is False, invalid
                too_large = json.loads(subtree_tool.invoke({"file_id": json_file_id,
                                                            "path": "/payload", "max_bytes": 256}))
                assert too_large["success"] is False, too_large
                outsider = tools_for_project(other_user_id, int(project_id), "ASK")
                outsider_structure = next(tool for tool in outsider if tool.name == "json_structure_read")
                denied_json = json.loads(outsider_structure.invoke({"file_id": json_file_id}))
                assert denied_json["success"] is False, denied_json

                real_json_model = os.getenv("DECKWISE_REAL_JSON_MODEL") == "1"
                model_service.resolve_chat_model = (original_model_resolver if real_json_model
                                                    else lambda _user_id, _model_id, _mode: ScriptedJsonModel())
                json_session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                           json={"title": "JSON 局部读取"})
                assert json_session.status_code == 200, json_session.text
                json_session_id = json_session.json()["data"]["id"]
                json_stream = client.post(f"/api/sessions/{json_session_id}/sendRPC", headers=headers,
                                          json={"message": "查看 config.json 中 beta 的状态。",
                                                "mode": "ASK", "model": "deepseek-chat"})
                assert json_stream.status_code == 200 and "event: done" in json_stream.text, json_stream.text[-1000:]
                json_events = [json.loads(line[6:]) for line in json_stream.text.splitlines()
                               if line.startswith("data: {")]
                json_tool_names = [event["name"] for event in json_events if event["type"] == "tool_call"]
                if real_json_model:
                    assert "json_structure_read" in json_tool_names and "json_subtree_read" in json_tool_names, json_tool_names
                else:
                    assert json_tool_names == ["file_list", "json_structure_read", "json_subtree_read"], json_tool_names
                    assert "beta 功能未启用" in json_stream.text
                print("JSON flow OK: structure, pointer subtree, bounded read, auth, SSE")

                image_key = data["files"][4]["cacheKey"]
                try:
                    file_service.image_input_url(other_user_id, int(project_id), image_key)
                    raise AssertionError("cross-user image access succeeded")
                except BusinessError as error:
                    assert error.status == 404
                try:
                    file_service.image_input_url(user_id, int(project_id), text_file["cacheKey"])
                    raise AssertionError("text file accepted as image")
                except BusinessError as error:
                    assert error.status == 400

                model_service.resolve_chat_model = lambda _user_id, _model_id, _mode: ScriptedImageModel()
                model_service.supports_images = lambda _user_id, model_id: model_id == "openai/gpt-6-luna"
                image_session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                            json={"title": "图片理解"})
                assert image_session.status_code == 200, image_session.text
                image_session_id = image_session.json()["data"]["id"]
                rejected = client.post(f"/api/sessions/{image_session_id}/sendRPC", headers=headers, json={
                    "message": "图中是什么？", "mode": "ASK", "model": "deepseek-chat",
                    "imageCacheKeys": [image_key],
                })
                assert rejected.status_code == 400 and "不支持图片" in rejected.text, rejected.text
                image_stream = client.post(f"/api/sessions/{image_session_id}/sendRPC", headers=headers, json={
                    "message": "图中是什么？", "mode": "ASK", "model": "openai/gpt-6-luna",
                    "imageCacheKeys": [image_key],
                })
                assert image_stream.status_code == 200 and "图中是红色方块" in image_stream.text
                assert "event: done" in image_stream.text
                image_history = client.get(f"/api/sessions/{image_session_id}/messages/after-seq", headers=headers)
                assert image_history.status_code == 200
                image_user = next(item for item in image_history.json()["data"] if item["role"] == "user")
                assert image_user["attachments"][0]["kind"] == "image"
                assert image_user["attachments"][0]["name"] == "red.png"
                assert "r2.cloudflarestorage.com" not in image_history.text
                print("image flow OK: private upload, DeepSeek rejection, OpenRouter model input, history")

            print("file flow OK: TXT/PDF/DOCX/JSON/PNG upload, R2 preview, fragments, Agent read")
    finally:
        model_service.resolve_chat_model = original_model_resolver
        model_service.supports_images = original_supports_images
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
