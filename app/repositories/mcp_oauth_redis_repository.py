"""One-use, session-bound Notion OAuth state and PKCE verifier."""

import hashlib
import json

from app.repositories.auth_redis_repository import get_redis

PREFIX = "deckwise-python:notion-mcp:oauth:"
STATE_TTL_SECONDS = 600
CONSUME_MATCHING = """
local raw = redis.call('GET', KEYS[1])
if not raw then return nil end
local data = cjson.decode(raw)
if tostring(data.user_id) ~= ARGV[1] or data.session_hash ~= ARGV[2] then
    return nil
end
redis.call('DEL', KEYS[1])
return raw
"""


def _key(state: str) -> str:
    return PREFIX + hashlib.sha256(state.encode()).hexdigest()


def put(state: str, payload: dict) -> None:
    stored = get_redis().set(_key(state), json.dumps(payload, separators=(",", ":")),
                             ex=STATE_TTL_SECONDS, nx=True)
    if not stored:
        raise RuntimeError("duplicate OAuth state")


def consume(state: str, user_id: int, session_hash: str) -> dict | None:
    raw = get_redis().eval(CONSUME_MATCHING, 1, _key(state), str(user_id), session_hash)
    return json.loads(raw) if raw else None
