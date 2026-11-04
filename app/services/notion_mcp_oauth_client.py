"""OAuth discovery, registration and token exchange for Notion's hosted MCP."""

from urllib.parse import urlencode, urlparse

import httpx

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

MCP_URL = "https://mcp.notion.com/mcp"
ORIGIN = "https://mcp.notion.com"
RESOURCE_METADATA_URL = f"{ORIGIN}/.well-known/oauth-protected-resource"
AUTH_METADATA_URL = f"{ORIGIN}/.well-known/oauth-authorization-server"
TIMEOUT = 12.0


class ReauthorizationRequired(Exception):
    """The Notion grant can no longer be refreshed."""


def _endpoint(value: object) -> str:
    if not isinstance(value, str) or urlparse(value).scheme != "https" or urlparse(value).netloc != "mcp.notion.com":
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 授权端点无效")
    return value


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=True) as client:
            return client.request(method, url, **kwargs)
    except httpx.HTTPError as error:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 授权服务暂时不可用") from error


def _json(response: httpx.Response, message: str) -> dict:
    if response.is_error:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, message)
    try:
        data = response.json()
    except ValueError as error:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, message) from error
    if not isinstance(data, dict):
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, message)
    return data


def discover() -> dict[str, str]:
    resource = _json(_request("GET", RESOURCE_METADATA_URL), "Notion MCP 元数据不可用")
    servers = resource.get("authorization_servers")
    if not isinstance(servers, list) or ORIGIN not in servers:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion MCP 授权服务不匹配")
    metadata = _json(_request("GET", AUTH_METADATA_URL), "Notion OAuth 元数据不可用")
    if metadata.get("issuer") != ORIGIN or "S256" not in metadata.get("code_challenge_methods_supported", []):
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion OAuth 配置不受支持")
    return {key: _endpoint(metadata.get(key)) for key in
            ("authorization_endpoint", "token_endpoint", "registration_endpoint")}


def register(redirect_uri: str, metadata: dict[str, str]) -> dict[str, str | None]:
    body = {
        "client_name": "Deckwise Python Demo",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    data = _json(_request("POST", metadata["registration_endpoint"], json=body),
                 "Notion MCP 客户端注册失败")
    client_id = data.get("client_id")
    if not isinstance(client_id, str) or not client_id:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion MCP 未返回客户端标识")
    secret = data.get("client_secret")
    return {"client_id": client_id, "client_secret": secret if isinstance(secret, str) else None}


def authorization_url(metadata: dict[str, str], client_id: str, redirect_uri: str,
                      state: str, code_challenge: str) -> str:
    params = urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
        "state": state, "code_challenge": code_challenge,
        "code_challenge_method": "S256", "scope": "default", "prompt": "consent",
    })
    return metadata["authorization_endpoint"] + "?" + params


def exchange(code: str, verifier: str, redirect_uri: str, client_id: str,
             client_secret: str | None, metadata: dict[str, str]) -> dict:
    body = {"grant_type": "authorization_code", "code": code,
            "client_id": client_id, "redirect_uri": redirect_uri, "code_verifier": verifier}
    if client_secret:
        body["client_secret"] = client_secret
    data = _json(_request("POST", metadata["token_endpoint"], data=body),
                 "Notion 授权交换失败，请重新连接")
    if not isinstance(data.get("access_token"), str) or not data["access_token"]:
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 未返回访问凭据")
    return data


def refresh(refresh_token: str, client_id: str, client_secret: str | None,
            metadata: dict[str, str]) -> dict:
    body = {"grant_type": "refresh_token", "refresh_token": refresh_token,
            "client_id": client_id}
    if client_secret:
        body["client_secret"] = client_secret
    response = _request("POST", metadata["token_endpoint"], data=body)
    if response.status_code == 400:
        try:
            if response.json().get("error") == "invalid_grant":
                raise ReauthorizationRequired
        except (ValueError, AttributeError):
            pass
    data = _json(response, "Notion 凭据刷新失败")
    if not isinstance(data.get("access_token"), str) or not isinstance(data.get("refresh_token"), str):
        raise BusinessError(502, ErrorCode.EXTERNAL_SERVICE_ERROR, "Notion 未返回轮换后的凭据")
    return data
