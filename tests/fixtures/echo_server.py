"""Standalone MCP test fixture server, run as a real subprocess over stdio.

Deliberately outside the `energyops_mcp` package and invoked by file path
(not `-m`) so tests don't depend on package/working-directory resolution --
it only needs `energyops_mcp` importable, which editable-installing the
project gives us in any interpreter that is the venv's own `python.exe`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from energyops_mcp.protocol.server import McpServer
from energyops_mcp.protocol.types import CallToolResult

server = McpServer(name="echo-fixture", version="0.1.0", page_size=2)


@server.tool(
    "add",
    "Add two numbers.",
    {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    },
)
def add(arguments: dict) -> CallToolResult:
    total = arguments["a"] + arguments["b"]
    return CallToolResult.ok(str(total), structured={"sum": total})


@server.tool("fail", "Always raises, to exercise the tool-failure path.", {"type": "object"})
def fail(arguments: dict) -> CallToolResult:
    raise RuntimeError("intentional failure for tests")


@server.tool(
    "slow",
    "Sleeps for the given number of seconds before responding.",
    {"type": "object", "properties": {"seconds": {"type": "number"}}, "required": ["seconds"]},
)
def slow(arguments: dict) -> CallToolResult:
    time.sleep(arguments["seconds"])
    return CallToolResult.ok("done")


@server.tool("tool_c", "Third tool, only used to exercise pagination.", {"type": "object"})
def tool_c(arguments: dict) -> CallToolResult:
    return CallToolResult.ok("c")


if __name__ == "__main__":
    server.run_stdio()
