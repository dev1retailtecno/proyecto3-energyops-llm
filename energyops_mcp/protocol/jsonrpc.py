"""JSON-RPC 2.0 message model: parsing, validation and serialization.

Implements the wire format defined at https://www.jsonrpc.org/specification.
This module knows nothing about MCP methods or transports; it only knows how
to turn Python objects into valid JSON-RPC 2.0 messages and back, and how to
reject malformed input with the correct standard error codes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

JSONRPC_VERSION = "2.0"

# Standard JSON-RPC 2.0 error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# -32000 to -32099 are reserved for implementation-defined server errors.
SERVER_ERROR = -32000

_STANDARD_MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
}

RequestId = str | int | None


class JsonRpcError(Exception):
    """A protocol-level JSON-RPC error (distinct from a tool execution failure).

    Raised when a message cannot be parsed/validated, or when a peer replies
    with a JSON-RPC error object. Never raised for MCP tool failures -- those
    are reported as an ``isError`` result on ``CallToolResult`` instead (see
    ``energyops_mcp.protocol.types``).
    """

    def __init__(self, code: int, message: str | None = None, data: Any = None):
        self.code = code
        self.message = message or _STANDARD_MESSAGES.get(code, "Server error")
        self.data = data
        super().__init__(f"[{self.code}] {self.message}")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass(frozen=True)
class JsonRpcRequest:
    id: RequestId
    method: str
    params: dict[str, Any] | list[Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": self.id, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d


@dataclass(frozen=True)
class JsonRpcNotification:
    method: str
    params: dict[str, Any] | list[Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d


@dataclass(frozen=True)
class JsonRpcResponse:
    id: RequestId
    result: Any = field(default=None)

    def to_wire(self) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": self.id, "result": self.result}


@dataclass(frozen=True)
class JsonRpcErrorResponse:
    id: RequestId
    error: JsonRpcError

    def to_wire(self) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": self.id, "error": self.error.to_dict()}


InboundMessage = JsonRpcRequest | JsonRpcNotification | JsonRpcResponse | JsonRpcErrorResponse


def serialize(message: InboundMessage) -> str:
    """Serialize a message to a single JSON line (no embedded newlines).

    stdio transport requires exactly one message per line; embedding a
    newline in the payload would desynchronize the reader.
    """
    line = json.dumps(message.to_wire(), separators=(",", ":"))
    if "\n" in line:
        raise ValueError("serialized JSON-RPC message must not contain a newline")
    return line


def parse_message(raw: str) -> InboundMessage:
    """Parse one line of text into a JSON-RPC 2.0 message.

    Raises JsonRpcError(PARSE_ERROR) on invalid JSON and
    JsonRpcError(INVALID_REQUEST) on a structurally invalid envelope, so
    callers can always reply with a spec-correct error.
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JsonRpcError(PARSE_ERROR, data=str(exc)) from exc

    if not isinstance(obj, dict):
        raise JsonRpcError(INVALID_REQUEST, data="message must be a JSON object")
    if obj.get("jsonrpc") != JSONRPC_VERSION:
        raise JsonRpcError(INVALID_REQUEST, data="missing or invalid 'jsonrpc' version")

    has_method = "method" in obj
    has_id = "id" in obj
    has_result = "result" in obj
    has_error = "error" in obj

    if has_method:
        method = obj["method"]
        if not isinstance(method, str) or not method:
            raise JsonRpcError(INVALID_REQUEST, data="'method' must be a non-empty string")
        params = obj.get("params")
        if params is not None and not isinstance(params, (dict, list)):
            raise JsonRpcError(INVALID_REQUEST, data="'params' must be an object or array")
        if has_id:
            req_id = obj["id"]
            if req_id is not None and not isinstance(req_id, (str, int)):
                raise JsonRpcError(INVALID_REQUEST, data="'id' must be a string, number or null")
            return JsonRpcRequest(id=req_id, method=method, params=params)
        return JsonRpcNotification(method=method, params=params)

    if has_result or has_error:
        if not has_id:
            raise JsonRpcError(INVALID_REQUEST, data="response is missing 'id'")
        req_id = obj["id"]
        if has_error:
            err_obj = obj["error"]
            if not isinstance(err_obj, dict) or "code" not in err_obj or "message" not in err_obj:
                raise JsonRpcError(INVALID_REQUEST, data="'error' must have 'code' and 'message'")
            return JsonRpcErrorResponse(
                id=req_id,
                error=JsonRpcError(
                    code=err_obj["code"], message=err_obj["message"], data=err_obj.get("data")
                ),
            )
        return JsonRpcResponse(id=req_id, result=obj.get("result"))

    raise JsonRpcError(INVALID_REQUEST, data="message has neither 'method' nor 'result'/'error'")
