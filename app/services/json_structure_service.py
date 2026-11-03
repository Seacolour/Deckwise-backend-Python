"""Bounded JSON Pointer navigation for project file tools."""

import json
import re

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

MAX_STRUCTURE_NODES = 100
MAX_STRUCTURE_BYTES = 16_000
MAX_SUBTREE_BYTES = 12_000
MAX_SUBTREE_NODES = 400


def _type(value: object) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def resolve_pointer(document: object, path: str) -> object:
    """Resolve RFC 6901 JSON Pointer; an empty path addresses the root."""
    if path == "":
        return document
    if len(path) > 1_000 or not path.startswith("/"):
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "JSON Pointer 必须以 / 开头")
    node = document
    for raw_token in path[1:].split("/"):
        if re.search(r"~(?![01])", raw_token):
            raise BusinessError(400, ErrorCode.PARAMS_ERROR, "JSON Pointer 转义无效")
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                raise BusinessError(404, ErrorCode.NOT_FOUND, "JSON 路径不存在")
            node = node[token]
        elif isinstance(node, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or int(token) >= len(node):
                raise BusinessError(404, ErrorCode.NOT_FOUND, "JSON 数组索引不存在")
            node = node[int(token)]
        else:
            raise BusinessError(404, ErrorCode.NOT_FOUND, "JSON 路径不存在")
    return node


def structure(document: object, path: str = "", max_depth: int = 2,
              max_keys: int = 20, sample_array_items: int = 3) -> dict:
    node = resolve_pointer(document, path)
    depth_limit = min(max(max_depth, 0), 4)
    key_limit = min(max(max_keys, 1), 30)
    item_limit = min(max(sample_array_items, 1), 5)
    budget = [MAX_STRUCTURE_NODES]

    def visit(value: object, pointer: str, depth: int) -> dict:
        budget[0] -= 1
        result: dict = {"path": pointer, "type": _type(value)}
        if isinstance(value, (dict, list)):
            result["size"] = len(value)
            if depth >= depth_limit or budget[0] <= 0:
                result["truncated"] = bool(value)
                return result
            if isinstance(value, dict):
                entries = [(str(key), child) for key, child in list(value.items())[:key_limit]]
                result["children"] = [
                    {"key": key, **visit(child, pointer + "/" + _escape(key), depth + 1)}
                    for key, child in entries if budget[0] > 0
                ]
            else:
                entries = list(enumerate(value[:item_limit]))
                result["children"] = [
                    {"index": index, **visit(child, pointer + "/" + str(index), depth + 1)}
                    for index, child in entries if budget[0] > 0
                ]
            result["truncated"] = len(result["children"]) < len(value)
        elif isinstance(value, str):
            result["preview"] = value[:120]
            result["length"] = len(value)
        else:
            result["value"] = value
        return result

    result = visit(node, path, 0)
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_STRUCTURE_BYTES:
        raise BusinessError(413, ErrorCode.PARAMS_ERROR, "结构视图过大，请缩小路径或深度")
    return result


def subtree(document: object, path: str = "", max_bytes: int = MAX_SUBTREE_BYTES,
            max_nodes: int = MAX_SUBTREE_NODES) -> dict:
    value = resolve_pointer(document, path)
    byte_limit = min(max(max_bytes, 256), MAX_SUBTREE_BYTES)
    node_limit = min(max(max_nodes, 1), MAX_SUBTREE_NODES)
    stack = [value]
    count = 0
    while stack:
        current = stack.pop()
        count += 1
        if count > node_limit:
            raise BusinessError(413, ErrorCode.PARAMS_ERROR, "JSON 子树节点过多，请读取更窄的路径")
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > byte_limit:
        raise BusinessError(413, ErrorCode.PARAMS_ERROR, "JSON 子树过大，请读取更窄的路径")
    return {"path": path, "type": _type(value), "nodes": count, "bytes": len(encoded), "value": value}
