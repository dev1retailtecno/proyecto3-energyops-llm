"""Client-level protocol tests against an in-memory fake transport.

No subprocess involved here -- these tests isolate id correlation, tolerance
of malformed inbound lines, and clean failure on transport close, which are
awkward to force deterministically against a real child process.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from energyops_mcp.protocol.client import McpClient, McpConnectionError

pytestmark = pytest.mark.asyncio


class FakeTransport:
    def __init__(self):
        self.sent: list[str] = []
        self._incoming: asyncio.Queue = asyncio.Queue()

    async def start(self) -> None:
        pass

    async def send(self, line: str) -> None:
        self.sent.append(line)

    async def receive_lines(self):
        while True:
            item = await self._incoming.get()
            if item is None:
                return
            yield item

    async def aclose(self) -> None:
        await self._incoming.put(None)

    async def push(self, line: str) -> None:
        await self._incoming.put(line)


def _canned_result_response(request_id, text: str) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": False},
        }
    )


async def test_interleaved_responses_correlate_by_id_not_order():
    transport = FakeTransport()
    client = McpClient(transport, server_name="fake")
    await client.start()

    call_a = asyncio.create_task(client.call_tool("a", {}))
    call_b = asyncio.create_task(client.call_tool("b", {}))
    await asyncio.sleep(0.05)

    assert len(transport.sent) == 2
    req_a = json.loads(transport.sent[0])
    req_b = json.loads(transport.sent[1])

    # Respond out of order: b's answer arrives before a's.
    await transport.push(_canned_result_response(req_b["id"], "B"))
    await transport.push(_canned_result_response(req_a["id"], "A"))

    result_a = await call_a
    result_b = await call_b
    assert result_a.text() == "A"
    assert result_b.text() == "B"

    await client.aclose()


async def test_malformed_inbound_line_is_ignored_not_fatal():
    transport = FakeTransport()
    client = McpClient(transport, server_name="fake")
    await client.start()

    call = asyncio.create_task(client.call_tool("a", {}))
    await asyncio.sleep(0.05)
    req = json.loads(transport.sent[0])

    await transport.push("{not valid json at all")
    await transport.push(_canned_result_response(req["id"], "ok"))

    result = await call
    assert result.is_error is False
    assert result.text() == "ok"

    await client.aclose()


async def test_unknown_response_id_is_ignored():
    """A response for an id we never sent (or already resolved) must not crash the client."""
    transport = FakeTransport()
    client = McpClient(transport, server_name="fake")
    await client.start()

    await transport.push(_canned_result_response(999, "orphan"))
    await asyncio.sleep(0.05)  # give the read loop a chance to process it

    call = asyncio.create_task(client.call_tool("a", {}))
    await asyncio.sleep(0.05)
    req = json.loads(transport.sent[0])
    await transport.push(_canned_result_response(req["id"], "ok"))

    result = await call
    assert result.text() == "ok"
    await client.aclose()


async def test_transport_close_fails_pending_requests():
    transport = FakeTransport()
    client = McpClient(transport, server_name="fake")
    await client.start()

    call = asyncio.create_task(client.call_tool("a", {}))
    await asyncio.sleep(0.05)

    await transport.aclose()  # simulate the child process exiting / pipe closing

    with pytest.raises(McpConnectionError):
        await call

    await client.aclose()


async def _respond_to_initialize(transport: FakeTransport, protocol_version: str) -> None:
    await asyncio.sleep(0.05)
    req = json.loads(transport.sent[0])
    await transport.push(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {
                    "protocolVersion": protocol_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "fake", "version": "0.0.0"},
                },
            }
        )
    )


async def test_initialize_accepts_an_older_known_protocol_revision():
    # A real classmate server (la-cava, mcp_drink_inventory) always negotiates
    # down to 2024-11-05 -- the revision before tool annotations existed --
    # regardless of the version we request. See SUPPORTED_PROTOCOL_VERSIONS
    # in client.py: this is real interoperability, not a relaxed check.
    transport = FakeTransport()
    client = McpClient(transport, server_name="fake")
    await client.start()

    init = asyncio.create_task(client.initialize())
    await _respond_to_initialize(transport, "2024-11-05")

    result = await init
    assert result["protocolVersion"] == "2024-11-05"
    assert client.server_info == {"name": "fake", "version": "0.0.0"}
    await client.aclose()


async def test_initialize_rejects_an_unknown_protocol_revision():
    transport = FakeTransport()
    client = McpClient(transport, server_name="fake")
    await client.start()

    init = asyncio.create_task(client.initialize())
    await _respond_to_initialize(transport, "1999-01-01")

    with pytest.raises(McpConnectionError):
        await init
    await client.aclose()
