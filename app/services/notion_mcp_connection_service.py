"""User-bound Notion MCP OAuth lifecycle; no Agent tools are exposed here."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.core.config import notion_mcp_redirect_uri
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.core.mcp_credential_cipher import decrypt, encrypt
from app.db.session import session_scope
from app.repositories import agent_plugin_repository, mcp_connection_repository, mcp_oauth_redis_repository
from app.services import notion_mcp_oauth_client

PROVIDER = "notion"
REFRESH_SKEW = timedelta(minutes=5)


def _session_hash(cookie: str | None) -> str:
    if not cookie:
        raise BusinessError(401, ErrorCode.TOKEN_INVALID, "登录状态已失效")
    return hashlib.sha256(cookie.encode()).hexdigest()


def _redirect_uri() -> str:
    uri = notion_mcp_redirect_uri()
    parsed = urlparse(uri)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "Notion MCP 回调地址配置无效")
    if parsed.path != "/oauth/notion-mcp/callback" or parsed.query or parsed.fragment or not parsed.netloc:
        raise BusinessError(503, ErrorCode.SYSTEM_BUSY, "Notion MCP 回调地址配置无效")
    return uri


def _stored(user_id: int, row: dict) -> dict:
    return decrypt(user_id, PROVIDER, row["credential_ciphertext"], row["nonce"], row["key_version"])


def connection_status(user_id: int) -> tuple[str, str | None]:
    with session_scope() as db:
        row = mcp_connection_repository.find(db, user_id)
    if row is None:
        return "disconnected", None
    if row["status"] == "authorizing" and row["updated_at"] < datetime.now(timezone.utc) - timedelta(minutes=10):
        return "disconnected", None
    return row["status"], row["workspace_name"]


def begin(user_id: int, session_cookie: str | None) -> str:
    redirect_uri = _redirect_uri()
    session_hash = _session_hash(session_cookie)
    metadata = notion_mcp_oauth_client.discover()
    with session_scope() as db:
        existing = mcp_connection_repository.find(db, user_id, lock=True)
        previous = _stored(user_id, existing) if existing else {}
        if previous.get("redirect_uri") == redirect_uri and previous.get("client_id"):
            client = {"client_id": previous["client_id"], "client_secret": previous.get("client_secret")}
        else:
            client = notion_mcp_oauth_client.register(redirect_uri, metadata)
        credential = {**client, "redirect_uri": redirect_uri}
        ciphertext, nonce, version = encrypt(user_id, PROVIDER, credential)
        mcp_connection_repository.upsert(db, user_id, PROVIDER, "authorizing",
                                         ciphertext, nonce, version)
        agent_plugin_repository.set_enabled(db, user_id, PROVIDER, False)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    mcp_oauth_redis_repository.put(state, {"user_id": user_id, "session_hash": session_hash,
                                            "verifier": verifier, "client_id": client["client_id"]})
    return notion_mcp_oauth_client.authorization_url(
        metadata, str(client["client_id"]), redirect_uri, state, challenge,
    )


def complete(user_id: int, session_cookie: str | None, code: str, state: str) -> None:
    if not code or not state or len(code) > 2048 or len(state) > 256:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 授权参数无效")
    session_hash = _session_hash(session_cookie)
    pending = mcp_oauth_redis_repository.consume(state, user_id, session_hash)
    if not pending:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 授权已过期或会话不匹配")
    with session_scope() as db:
        row = mcp_connection_repository.find(db, user_id)
    if row is None or row["status"] != "authorizing":
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 授权状态已失效")
    credential = _stored(user_id, row)
    if credential.get("client_id") != pending.get("client_id"):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 授权客户端已变更")
    metadata = notion_mcp_oauth_client.discover()
    token = notion_mcp_oauth_client.exchange(
        code, pending["verifier"], credential["redirect_uri"], credential["client_id"],
        credential.get("client_secret"), metadata,
    )
    expires_in = token.get("expires_in")
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat() \
        if isinstance(expires_in, (int, float)) and expires_in > 0 else None
    credential.update(access_token=token["access_token"], refresh_token=token.get("refresh_token"),
                      expires_at=expiry)
    ciphertext, nonce, version = encrypt(user_id, PROVIDER, credential)
    with session_scope() as db:
        current = mcp_connection_repository.find(db, user_id, lock=True)
        if current is None or current["status"] != "authorizing":
            raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 授权状态已失效")
        if _stored(user_id, current).get("client_id") != credential["client_id"]:
            raise BusinessError(400, ErrorCode.PARAMS_ERROR, "Notion 授权客户端已变更")
        mcp_connection_repository.upsert(db, user_id, PROVIDER, "connected",
                                         ciphertext, nonce, version,
                                         str(token.get("workspace_id") or "") or None,
                                         str(token.get("workspace_name") or "") or None)
        agent_plugin_repository.set_enabled(db, user_id, PROVIDER, True)


def disconnect(user_id: int) -> bool:
    with session_scope() as db:
        deleted = mcp_connection_repository.delete(db, user_id)
        agent_plugin_repository.set_enabled(db, user_id, PROVIDER, False)
    return deleted


def access_token(user_id: int) -> str:
    """Refresh under a row lock so rotating refresh tokens cannot race."""
    reauthorization_required = False
    value: str | None = None
    with session_scope() as db:
        row = mcp_connection_repository.find(db, user_id, lock=True)
        if row is None or row["status"] != "connected":
            raise BusinessError(409, ErrorCode.REVISION_CONFLICT, "请先连接 Notion")
        credential = _stored(user_id, row)
        expiry = datetime.fromisoformat(credential["expires_at"]) if credential.get("expires_at") else None
        if expiry is None or expiry > datetime.now(timezone.utc) + REFRESH_SKEW:
            value = credential.get("access_token")
        elif not credential.get("refresh_token"):
            reauthorization_required = True
        else:
            metadata = notion_mcp_oauth_client.discover()
            try:
                token = notion_mcp_oauth_client.refresh(
                    credential["refresh_token"], credential["client_id"],
                    credential.get("client_secret"), metadata,
                )
            except notion_mcp_oauth_client.ReauthorizationRequired:
                reauthorization_required = True
            else:
                expires_in = token.get("expires_in")
                credential.update(access_token=token["access_token"],
                                  refresh_token=token["refresh_token"],
                                  expires_at=(datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
                                  if isinstance(expires_in, (int, float)) and expires_in > 0 else None)
                ciphertext, nonce, version = encrypt(user_id, PROVIDER, credential)
                mcp_connection_repository.upsert(db, user_id, PROVIDER, "connected", ciphertext,
                                                 nonce, version, row["workspace_id"], row["workspace_name"])
                value = credential["access_token"]
        if reauthorization_required or not value:
            mcp_connection_repository.set_status(db, user_id, PROVIDER, "reconnect_required")
            agent_plugin_repository.set_enabled(db, user_id, PROVIDER, False)
    if reauthorization_required or not value:
        raise BusinessError(409, ErrorCode.REVISION_CONFLICT, "Notion 授权已失效，请重新连接")
    return value
