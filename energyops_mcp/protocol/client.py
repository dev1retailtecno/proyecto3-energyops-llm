"""MCP client: connection lifecycle over any transport exposing send/receive_lines/aclose.

Handles request/response correlation by id, interleaved responses, server-initiated
requests (e.g. roots/list), notifications, timeouts and cancellation, and clean
shutdown. Transport-agnostic: works with StdioTransport today and the Streamable
HTTP transport later, since both only need to satisfy the same small interface.

Protocol errors vs. tool failures are kept structurally distinct:
- A malformed message, unknown method or transport failure raises JsonRpcError.
- A tool that runs but fails returns normally as CallToolResult(is_error=True).
This lets the host tell "MCP is broken" apart from "the tool reported a failure",
per the project's requirement to separate protocol errors from execution failures.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, Self

from .interaction_log import InteractionLogger
from .jsonrpc import (
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    JsonRpcError,
    JsonRpcErrorResponse,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    RequestId,
    parse_message,
    serialize,
)
from .types import CallToolResult, Tool

MCP_PROTOCOL_VERSION = "2025-06-18"

# Revisions this client can speak, newest first. We always *request*
# MCP_PROTOCOL_VERSION, but a server is allowed to negotiate down to an
# older revision it supports instead of echoing ours back -- and a real
# classmate server we connect to in practice does exactly that (always
# replies "2024-11-05", the revision before tool annotations existed,
# without even reading what we asked for). The wire shape of the messages
# this client actually sends (initialize, notifications/initialized,
# tools/list, tools/call) is unchanged across these three revisions, so
# accepting any of them is a real interoperability fix, not a weakened
# check: an unlisted version is still rejected.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

ServerRequestHandler = Callable[[Any], Awaitable[Any]]
NotificationHandler = Callable[[Any], Awaitable[None]]


class Transport(Protocol):
    async def start(self) -> None: ...
    async def send(self, line: str) -> None: ...
    def receive_lines(self): ...
    async def aclose(self) -> None: ...


class McpConnectionError(JsonRpcError):
    """Raised when the transport closes or fails outside of a JSON-RPC error reply."""


class McpClient:
    def __init__(
        self,
        transport: Transport,
        server_name: str,
        logger: InteractionLogger | None = None,
        request_timeout: float = 30.0,
    ):
        self._transport = transport
        self.server_name = server_name
        self._logger = logger
        self._request_timeout = request_timeout
        self._next_id = 1
        self._pending: dict[RequestId, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._server_request_handlers: dict[str, ServerRequestHandler] = {}
        self._notification_handlers: dict[str, NotificationHandler] = {}
        self._closed = False
        self.server_info: dict[str, Any] | None = None
        self.server_capabilities: dict[str, Any] | None = None

    # --- connection setup -------------------------------------------------

    async def start(self) -> None:
        await self._transport.start()
        self._reader_task = asyncio.create_task(self._read_loop())

    async def initialize(
        self,
        client_name: str = "energyops",
        client_version: str = "0.1.0",
        capabilities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": capabilities if capabilities is not None else {},
                "clientInfo": {"name": client_name, "version": client_version},
            },
        )
        negotiated = result.get("protocolVersion")
        if negotiated not in SUPPORTED_PROTOCOL_VERSIONS:
            raise McpConnectionError(
                INTERNAL_ERROR,
                f"server negotiated unsupported protocol version {negotiated!r}; "
                f"this client only implements {SUPPORTED_PROTOCOL_VERSIONS!r}",
            )
        self.server_info = result.get("serverInfo")
        self.server_capabilities = result.get("capabilities")
        await self._notify("notifications/initialized")
        return result

    # --- MCP operations -----------------------------------------------------

    async def ping(self) -> None:
        await self._request("ping", {})

    async def list_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"cursor": cursor} if cursor else {}
            result = await self._request("tools/list", params)
            tools.extend(Tool.from_wire(t) for t in result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any], timeout: float | None = None
    ) -> CallToolResult:
        result = await self._request("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        return CallToolResult.from_wire(result)

    def on_server_request(self, method: str, handler: ServerRequestHandler) -> None:
        self._server_request_handlers[method] = handler

    def on_notification(self, method: str, handler: NotificationHandler) -> None:
        self._notification_handlers[method] = handler

    # --- low-level request/notification plumbing ----------------------------

    async def _request(
        self, method: str, params: dict[str, Any] | list[Any] | None = None, timeout: float | None = None
    ) -> Any:
        req_id = self._next_id
        self._next_id += 1
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        start = time.monotonic()
        try:
            async with asyncio.timeout(timeout or self._request_timeout):
                await self._send_message(JsonRpcRequest(id=req_id, method=method, params=params))
                result = await fut
            return result
        except TimeoutError:
            await self._notify("notifications/cancelled", {"requestId": req_id, "reason": "timeout"})
            raise McpConnectionError(INTERNAL_ERROR, f"timeout waiting for {method!r} response") from None
        finally:
            # Unconditional: if send() itself raised (transport failure before
            # any response could ever arrive), the future must still be
            # dropped from _pending here -- otherwise it sits unresolved until
            # the reader loop's eventual _fail_all_pending() sets an exception
            # nobody is awaiting anymore ("Future exception was never retrieved").
            self._pending.pop(req_id, None)
            elapsed_ms = (time.monotonic() - start) * 1000
            if self._logger:
                self._logger.log(
                    server=self.server_name,
                    direction="out",
                    payload={"method": method, "id": req_id},
                    duration_ms=elapsed_ms,
                    outcome="completed" if fut.done() and not fut.cancelled() else "timeout",
                )

    async def _notify(self, method: str, params: dict[str, Any] | list[Any] | None = None) -> None:
        await self._send_message(JsonRpcNotification(method=method, params=params))

    async def _send_message(self, msg: JsonRpcRequest | JsonRpcNotification | JsonRpcResponse | JsonRpcErrorResponse) -> None:
        line = serialize(msg)
        await self._transport.send(line)
        if self._logger:
            self._logger.log(server=self.server_name, direction="out", payload=msg.to_wire())

    # --- inbound message handling --------------------------------------------

    async def _read_loop(self) -> None:
        try:
            async for line in self._transport.receive_lines():
                try:
                    msg = parse_message(line)
                except JsonRpcError:
                    continue  # malformed line from the peer; nothing to correlate it to
                await self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - propagate reader failures to pending requests
            self._fail_all_pending(McpConnectionError(INTERNAL_ERROR, str(exc)))
        finally:
            self._fail_all_pending(McpConnectionError(INTERNAL_ERROR, "transport closed"))

    def _fail_all_pending(self, exc: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    async def _dispatch(self, msg: object) -> None:
        if isinstance(msg, (JsonRpcResponse, JsonRpcErrorResponse)):
            if self._logger:
                self._logger.log(server=self.server_name, direction="in", payload=msg.to_wire())
            fut = self._pending.pop(msg.id, None)
            if fut is None or fut.done():
                return
            if isinstance(msg, JsonRpcErrorResponse):
                fut.set_exception(msg.error)
            else:
                fut.set_result(msg.result)
        elif isinstance(msg, JsonRpcRequest):
            if self._logger:
                self._logger.log(server=self.server_name, direction="in", payload=msg.to_wire())
            await self._handle_server_request(msg)
        elif isinstance(msg, JsonRpcNotification):
            if self._logger:
                self._logger.log(server=self.server_name, direction="in", payload=msg.to_wire())
            handler = self._notification_handlers.get(msg.method)
            if handler is not None:
                await handler(msg.params)

    async def _handle_server_request(self, msg: JsonRpcRequest) -> None:
        handler = self._server_request_handlers.get(msg.method)
        if handler is None:
            await self._send_message(
                JsonRpcErrorResponse(
                    id=msg.id,
                    error=JsonRpcError(METHOD_NOT_FOUND, f"Unknown method: {msg.method}"),
                )
            )
            return
        try:
            result = await handler(msg.params)
            await self._send_message(JsonRpcResponse(id=msg.id, result=result))
        except JsonRpcError as exc:
            await self._send_message(JsonRpcErrorResponse(id=msg.id, error=exc))
        except Exception as exc:  # noqa: BLE001 - must not crash the read loop
            await self._send_message(JsonRpcErrorResponse(id=msg.id, error=JsonRpcError(INTERNAL_ERROR, str(exc))))

    # --- shutdown -------------------------------------------------------------

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._fail_all_pending(McpConnectionError(INTERNAL_ERROR, "client closed"))
        await self._transport.aclose()

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
