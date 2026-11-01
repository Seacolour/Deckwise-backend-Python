"""Short-lived login codes and opaque Web sessions in Redis."""

import hashlib
import hmac
from functools import lru_cache

import redis

from app.core.config import redis_url
from app.core.security import CODE_COOLDOWN, CODE_LIFETIME, MAX_CODE_ATTEMPTS, SESSION_LIFETIME, code_digest, token_digest

PREFIX = "deckwise-python:login:"

ISSUE_CODE = """
if redis.call('SET', KEYS[2], '1', 'EX', ARGV[3], 'NX') then
    redis.call('HSET', KEYS[1], 'salt', ARGV[1], 'digest', ARGV[2], 'attempts', 0)
    redis.call('EXPIRE', KEYS[1], ARGV[4])
    return 1
end
return 0
"""

CONSUME_CODE = """
if redis.call('HGET', KEYS[1], 'salt') ~= ARGV[1]
    or redis.call('HGET', KEYS[1], 'digest') ~= ARGV[2] then
    return 0
end
if tonumber(redis.call('HGET', KEYS[1], 'attempts') or '0') >= tonumber(ARGV[3]) then
    redis.call('DEL', KEYS[1])
    return 0
end
if ARGV[4] == '1' then
    redis.call('DEL', KEYS[1])
    return 1
end
if redis.call('HINCRBY', KEYS[1], 'attempts', 1) >= tonumber(ARGV[3]) then
    redis.call('DEL', KEYS[1])
end
return 0
"""

REMOVE_IF_MATCHES = """
if redis.call('HGET', KEYS[1], 'digest') == ARGV[1] then
    redis.call('DEL', KEYS[1], KEYS[2])
end
"""


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(redis_url(), socket_connect_timeout=2, socket_timeout=2)


def _email_keys(email: str) -> tuple[str, str]:
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    return f"{PREFIX}email-code:{email_hash}", f"{PREFIX}email-cooldown:{email_hash}"


def _session_key(token: str) -> str:
    return f"{PREFIX}session:{token_digest(token).hex()}"


def issue_login_code(email: str, salt: bytes, digest: bytes) -> bool:
    code_key, cooldown_key = _email_keys(email)
    return bool(get_redis().eval(
        ISSUE_CODE, 2, code_key, cooldown_key, salt.hex(), digest.hex(),
        int(CODE_COOLDOWN.total_seconds()), int(CODE_LIFETIME.total_seconds()),
    ))


def remove_login_code_if_matches(email: str, digest: bytes) -> None:
    code_key, cooldown_key = _email_keys(email)
    get_redis().eval(REMOVE_IF_MATCHES, 2, code_key, cooldown_key, digest.hex())


def consume_login_code(email: str, code: str) -> bool:
    code_key, _ = _email_keys(email)
    fields = get_redis().hmget(code_key, "salt", "digest")
    if not all(fields):
        return False
    salt, stored_digest = fields
    valid = hmac.compare_digest(code_digest(code, bytes.fromhex(salt.decode())), bytes.fromhex(stored_digest.decode()))
    return bool(get_redis().eval(
        CONSUME_CODE, 1, code_key, salt.decode(), stored_digest.decode(), MAX_CODE_ATTEMPTS, int(valid),
    ))


def create_web_session(token: str, user_id: int) -> None:
    get_redis().set(_session_key(token), str(user_id), ex=int(SESSION_LIFETIME.total_seconds()))


def get_session_user_id(token: str) -> int | None:
    value = get_redis().get(_session_key(token))
    return int(value) if value is not None else None


def revoke_web_session(token: str) -> None:
    get_redis().delete(_session_key(token))
