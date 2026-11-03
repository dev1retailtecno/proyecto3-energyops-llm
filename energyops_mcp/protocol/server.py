"""Base class for a stdio MCP server: reads JSON-RPC from stdin, writes to stdout.

Runs a synchronous read-eval-write loop -- deliberately not asyncio. A local
tool server talks to exactly one client over one pipe and processes one
request at a time, so blocking line I/O is simpler and sidesteps the
well-known fragility of piping a process's own stdin/stdout through asyncio
on Windows. The client side (energyops_mcp.protocol.client + stdio_transport)
is asyncio-based because a host application manages the child *subprocess*
concurrently with everything else it is doing, which is the well-supported
case on every platform via asyncio.create_subprocess_exec.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jsonschema

from .jsonrpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcError,
    JsonRpcErrorResponse,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    parse_message,
    serialize,
)
from .types import CallToolResult, Tool

MCP_PROTOCOL_VERSION = "2025-06-18"

ToolHandler = Callable[[dict[str, Any]], CallToolResult]


@dataclass
class RegisteredTool:
    tool: Tool
    handler: ToolHandler


class McpServer:
    """Register tools with @server.tool(...) then call server.run_stdio()."""

    def __init__(self, name: str, version: str, page_size: int = 50):
        self.name = name
        self.version = version
        self._tools: dict[str, RegisteredTool] = {}
        self._page_size = page_size

    def tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(fn: ToolHandler) -> ToolHandler:
            self._tools[name] = RegisteredTool(
                tool=Tool(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                    output_schema=output_schema,
                ),
                handler=fn,
            )
            return fn

        return decorator

    def run_stdio(self) -> None:
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass  # reconfigure() is unavailable if stdio was replaced (e.g. in tests)
        self._log(f"{self.name} v{self.version} MCP server ready on stdio")
        for raw in sys.stdin:
            text = raw.rstrip("\r\n")
            if text:
                self._handle_line(text)
        self._log(f"{self.name}: stdin closed, exiting")

    def _log(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    def _handle_line(self, text: str) -> None:
        try:
            msg = parse_message(text)
        except JsonRpcError as exc:
            self._write(JsonRpcErrorResponse(id=None, error=exc))
            return

        if isinstance(msg, JsonRpcNotification):
            self._log(f"notification: {msg.method}")
            return  # notifications never receive a response

        if not isinstance(msg, JsonRpcRequest):
            return  # an unsolicited response/error; nothing to correlate it to

        try:
            result = self._dispatch_request(msg)
            self._write(JsonRpcResponse(id=msg.id, result=result))
        except JsonRpcError as exc:
            self._write(JsonRpcErrorResponse(id=msg.id, error=exc))
        except Exception as exc:  # noqa: BLE001 - must not crash the server loop
            self._log(f"internal error handling {msg.method}: {exc!r}")
            self._write(JsonRpcErrorResponse(id=msg.id, error=JsonRpcError(INTERNAL_ERROR, str(exc))))

    def _write(self, msg: JsonRpcResponse | JsonRpcErrorResponse) -> None:
        sys.stdout.write(serialize(msg) + "\n")
        sys.stdout.flush()

    def _dispatch_request(self, msg: JsonRpcRequest) -> Any:
        if msg.params is not None and not isinstance(msg.params, dict):
            raise JsonRpcError(INVALID_PARAMS, "MCP parameters must be an object")
        if msg.method == "initialize":
            return {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            }
        if msg.method == "ping":
            return {}
        if msg.method == "tools/list":
            return self._list_tools(msg.params or {})
        if msg.method == "tools/call":
            return self._call_tool(msg.params or {})
        raise JsonRpcError(METHOD_NOT_FOUND, f"Unknown method: {msg.method}")

    def _list_tools(self, params: dict[str, Any]) -> dict[str, Any]:
        names = sorted(self._tools.keys())
        cursor = params.get("cursor")
        start = 0
        if cursor is not None:
            try:
                start = names.index(cursor) + 1
            except ValueError:
                raise JsonRpcError(INVALID_PARAMS, f"invalid cursor: {cursor!r}") from None
        page = names[start : start + self._page_size]
        next_cursor = page[-1] if start + self._page_size < len(names) else None
        return {"tools": [self._tools[n].tool.to_wire() for n in page], "nextCursor": next_cursor}

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or name not in self._tools:
            raise JsonRpcError(INVALID_PARAMS, f"unknown tool: {name!r}")
        arguments = params.get("arguments", {})
        registered = self._tools[name]
        try:
            jsonschema.validate(arguments, registered.tool.input_schema)
        except jsonschema.ValidationError as exc:
            raise JsonRpcError(INVALID_PARAMS, exc.message) from None
        try:
            result = registered.handler(arguments)
        except JsonRpcError:
            raise
        except Exception as exc:  # noqa: BLE001 - a tool failure is data, not a protocol error
            result = CallToolResult.error(f"{type(exc).__name__}: {exc}")
        return result.to_wire()
