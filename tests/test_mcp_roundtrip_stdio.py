"""End-to-end test: a real child process speaking MCP over real stdio pipes.

This is the "llamada completa" (complete call) proof for the local MCP
transport -- everything in test_mcp_client_fake_transport.py is a unit test
against a fake; this one spawns tests/fixtures/echo_server.py for real.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from energyops_mcp.protocol.client import McpClient, McpConnectionError
from energyops_mcp.protocol.jsonrpc import INVALID_PARAMS, JsonRpcError
from energyops_mcp.protocol.stdio_transport import StdioTransport

pytestmark = pytest.mark.asyncio

FIXTURE = Path(__file__).parent / "fixtures" / "echo_server.py"


async def _connected_client(**kwargs) -> McpClient:
    transport = StdioTransport(sys.executable, [str(FIXTURE)])
    client = McpClient(transport, server_name="echo-fixture", request_timeout=kwargs.pop("request_timeout", 10))
    await client.start()
    await client.initialize()
    return client


async def test_initialize_negotiates_and_returns_server_info():
    client = await _connected_client()
    try:
        assert client.server_info["name"] == "echo-fixture"
    finally:
        await client.aclose()


async def test_tools_list_paginates_across_multiple_pages():
    # the fixture server uses page_size=2 with 4 tools registered, forcing pagination
    client = await _connected_client()
    try:
        tools = await client.list_tools()
        assert {t.name for t in tools} == {"add", "fail", "slow", "tool_c"}
    finally:
        await client.aclose()


async def test_call_tool_success_returns_structured_content():
    client = await _connected_client()
    try:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        assert result.is_error is False
        assert result.text() == "5"
        assert result.structured_content == {"sum": 5}
    finally:
        await client.aclose()


async def test_tool_execution_failure_is_a_normal_result_not_an_exception():
    client = await _connected_client()
    try:
        result = await client.call_tool("fail", {})
        assert result.is_error is True
        assert "intentional failure" in result.text()
    finally:
        await client.aclose()


async def test_unknown_tool_name_is_a_protocol_error_not_a_result():
    client = await _connected_client()
    try:
        with pytest.raises(JsonRpcError) as exc_info:
            await client.call_tool("does_not_exist", {})
        assert exc_info.value.code == INVALID_PARAMS
    finally:
        await client.aclose()


async def test_ping_succeeds():
    client = await _connected_client()
    try:
        await client.ping()
    finally:
        await client.aclose()


async def test_client_side_timeout_raises_connection_error_and_cleans_up():
    client = await _connected_client(request_timeout=10)
    try:
        with pytest.raises(McpConnectionError):
            await client.call_tool("slow", {"seconds": 1}, timeout=0.2)
    finally:
        await client.aclose()
    assert client._closed is True
