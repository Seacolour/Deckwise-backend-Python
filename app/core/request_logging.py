"""HTTP request correlation and timing without logging credentials or bodies."""

import json
import logging
import re
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import is_dev_environment

logger = logging.getLogger("uvicorn.error")
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_MAX_BODY_BYTES = 8192
_SENSITIVE_KEY_PARTS = ("password", "passcode", "token", "apikey", "secret", "credential", "nonce", "code", "state")


def _request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-request-id":
            candidate = value.decode("ascii", errors="ignore")
            if _REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
    return uuid4().hex


def _redact(value: object, depth: int = 0) -> object:
    if depth >= 8:
        return "<max-depth>"
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("_", "").replace("-", "")
            redacted[str(key)] = (
                "<redacted>" if any(part in normalized for part in _SENSITIVE_KEY_PARTS)
                else _redact(item, depth + 1)
            )
        return redacted
    if isinstance(value, list):
        return [_redact(item, depth + 1) for item in value[:30]]
    if isinstance(value, str) and len(value) > 1024:
        return value[:1024] + "<truncated>"
    return value


def _safe_json_body(scope: Scope, captured: bytes, truncated: bool) -> str | None:
    content_type = next(
        (value.decode("latin-1").split(";", 1)[0].strip().lower()
         for name, value in scope.get("headers", []) if name.lower() == b"content-type"),
        "",
    )
    if content_type != "application/json" and not content_type.endswith("+json"):
        return None
    if not captured:
        return None
    if truncated:
        return f"<truncated after {_MAX_BODY_BYTES} bytes>"
    try:
        return json.dumps(_redact(json.loads(captured)), ensure_ascii=False, separators=(",", ":"))
    except (UnicodeDecodeError, ValueError, TypeError):
        return "<invalid-json>"


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "-"
        status = 500
        failure_type: str | None = None
        started = time.perf_counter()
        capture_body = is_dev_environment()
        captured = bytearray()
        truncated = False
        logger.info("request start id=%s method=%s path=%s client=%s", request_id, method, path, client_ip)

        async def receive_with_capture() -> Message:
            nonlocal truncated
            message = await receive()
            if capture_body and message["type"] == "http.request":
                chunk = message.get("body", b"")
                remaining = _MAX_BODY_BYTES - len(captured)
                if remaining > 0:
                    captured.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
            return message

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive_with_capture, send_with_request_id)
        except BaseException as error:
            failure_type = type(error).__name__
            raise
        finally:
            if capture_body:
                summary = _safe_json_body(scope, bytes(captured), truncated)
                if summary is not None:
                    logger.info("request body id=%s json=%s", request_id, summary)
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "request end id=%s method=%s path=%s status=%s duration_ms=%.1f failure=%s",
                request_id, method, path, status, elapsed_ms, failure_type or "-",
            )
