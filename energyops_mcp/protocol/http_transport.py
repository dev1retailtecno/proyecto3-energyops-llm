"""Streamable HTTP client transport: POST/GET to a single /mcp endpoint.

Bridges request/response HTTP onto the same send()/receive_lines()/aclose()
interface StdioTransport exposes, so McpClient's id-correlation, pagination
and lifecycle logic works completely unchanged regardless of transport.
Each POST's JSON (or SSE) response is pushed onto an internal queue that
receive_lines() drains -- this is what lets one McpClient implementation
serve both a child process over stdio and a remote HTTPS endpoint.

Handles the `application/json` and `text/event-stream` Streamable HTTP
response modes on the client side (our own tariff server only ever uses
the former, but a spec-compliant client should tolerate either). Respects
an `Mcp-Session-Id` returned by the server, per the MCP 2025-06-18
transport spec, echoing it back on subsequent requests.
"""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator

import httpx

from .jsonrpc import INTERNAL_ERROR, JsonRpcError

MCP_PROTOCOL_VERSION = "2025-06-18"


class HttpTransport:
    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        ssl_context: ssl.SSLContext | bool = True,
        headers: dict[str, str] | None = None,
    ):
        self._url = url
        self._timeout = timeout
        self._ssl_context = ssl_context
        self._extra_headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._incoming: asyncio.Queue[str | None] = asyncio.Queue()

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=self._timeout, verify=self._ssl_context)

    async def send(self, line: str) -> None:
        if self._client is None:
            raise RuntimeError("transport not started")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            **self._extra_headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            async with self._client.stream("POST", self._url, content=line.encode("utf-8"), headers=headers) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self._session_id = session_id
                if response.status_code == 202:
                    return
                if response.status_code >= 400:
                    await response.aread()
                    raise JsonRpcError(INTERNAL_ERROR, f"HTTP {response.status_code} from {self._url}")
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    data = []
                    async for raw_line in response.aiter_lines():
                        if raw_line == "":
                            if data:
                                await self._incoming.put("\n".join(data))
                                data = []
                        elif raw_line.startswith("data:"):
                            data.append(raw_line[5:].lstrip(" "))
                    if data:
                        await self._incoming.put("\n".join(data))
                elif "application/json" in content_type:
                    await response.aread()
                    await self._incoming.put(response.text)
                else:
                    raise JsonRpcError(INTERNAL_ERROR, f"Unsupported response type: {content_type}")
                return
        except httpx.TransportError as exc:
            raise JsonRpcError(INTERNAL_ERROR, f"HTTP transport error: {exc}") from exc

    async def receive_lines(self) -> AsyncIterator[str]:
        while True:
            item = await self._incoming.get()
            if item is None:
                return
            yield item

    async def aclose(self) -> None:
        await self._incoming.put(None)
        if self._client is not None:
            await self._client.aclose()
