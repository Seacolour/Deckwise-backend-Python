"""Verify the Web response contract and request log boundaries."""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import handle_unexpected_error
from app.db.checkpoint import selector_loop_factory
from app.core.request_logging import RequestLogMiddleware
from app.main import app


def test_request_id_and_logs_exclude_query_values(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app, backend_options={"loop_factory": selector_loop_factory}).get(
            "/hello/User?apiKey=should-not-appear-in-logs",
            headers={"X-Request-ID": "test-request-123"},
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-123"
    assert "request start id=test-request-123" in caplog.text
    assert "request end id=test-request-123" in caplog.text
    assert "status=200" in caplog.text
    assert "should-not-appear-in-logs" not in caplog.text


def test_dev_body_logs_business_fields_but_redacts_credentials(caplog, monkeypatch) -> None:
    monkeypatch.setenv("DECKWISE_ENV", "dev")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app, backend_options={"loop_factory": selector_loop_factory}).post(
            "/api/user/login",
            json={"email": "bad-email", "code": "123456", "apiKey": "private-api-key", "state": "oauth-state-value"},
        )

    assert response.status_code == 422
    assert '"email":"bad-email"' in caplog.text
    assert '"code":"<redacted>"' in caplog.text
    assert '"apiKey":"<redacted>"' in caplog.text
    assert '"state":"<redacted>"' in caplog.text
    assert "123456" not in caplog.text
    assert "private-api-key" not in caplog.text
    assert "oauth-state-value" not in caplog.text


def test_prod_body_is_not_logged(caplog, monkeypatch) -> None:
    monkeypatch.setenv("DECKWISE_ENV", "prod")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(app, backend_options={"loop_factory": selector_loop_factory}).post(
            "/api/user/login",
            json={"email": "bad-email", "code": "123456"},
        )

    assert response.status_code == 422
    assert "request body" not in caplog.text


def test_validation_and_missing_routes_use_web_error_envelope() -> None:
    with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
        invalid = client.post("/api/user/login", json={"email": "bad-email", "code": "123456"})
        missing = client.get("/api/unknown")
        unauthenticated = client.get("/api/user/get/login")

    assert invalid.status_code == 422
    assert invalid.json() == {"code": 40010, "data": None, "message": "请求参数校验失败: body.email"}
    assert missing.status_code == 404 and missing.json()["code"] == 40400
    assert unauthenticated.status_code == 401 and unauthenticated.json()["code"] == 40102
    assert all("x-request-id" in response.headers for response in (invalid, missing, unauthenticated))


def test_unexpected_error_hides_exception_message(caplog) -> None:
    isolated = FastAPI()
    isolated.add_middleware(RequestLogMiddleware)
    isolated.add_exception_handler(Exception, handle_unexpected_error)

    @isolated.get("/failure")
    def fail() -> None:
        raise RuntimeError("private-value-in-exception")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = TestClient(isolated, raise_server_exceptions=False).get("/failure")

    assert response.status_code == 500
    assert response.json() == {"code": 50000, "data": None, "message": "系统内部异常"}
    assert "x-request-id" in response.headers
    assert "private-value-in-exception" not in caplog.text
