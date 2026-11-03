"""stdio transport: spawn a child process and exchange newline-delimited JSON.

Per MCP transport rules: stdout carries JSON-RPC messages exclusively (one
per line, no embedded newlines); stderr is free-form diagnostics and is never
parsed as protocol. A dedicated stderr-draining task prevents the child from
blocking on a full stderr pipe.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from collections.abc import AsyncIterator, Callable


def resolve_windows_shim(command: str, args: list[str]) -> tuple[str, list[str]]:
    """Route npm-installed CLI shims (npx, npm, ...) through cmd.exe on Windows.

    asyncio.create_subprocess_exec calls Win32 CreateProcess directly, which
    -- unlike an interactive shell -- never resolves PATHEXT or re-invokes
    cmd.exe itself, so it cannot launch a .cmd/.bat file even given its full
    path. This affects any official or classmate MCP server distributed as
    an npm package (e.g. @modelcontextprotocol/server-filesystem via npx).
    A no-op on every other platform and for any command that isn't a
    .cmd/.bat shim.
    """
    if sys.platform != "win32":
        return command, args
    resolved = shutil.which(command)
    if resolved and resolved.lower().endswith((".cmd", ".bat")):
        comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        return comspec, ["/c", command, *args]
    return command, args


class StdioTransport:
    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stderr_sink: Callable[[str], None] | None = None,
    ):
        self._command = command
        self._args = args or []
        self._cwd = cwd
        self._env = env
        self._stderr_sink = stderr_sink
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task | None = None

    async def start(self) -> None:
        command, args = resolve_windows_shim(self._command, self._args)
        self._proc = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
            env=self._env,
            limit=8 * 1024 * 1024,
        )
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        try:
            async for raw in self._proc.stderr:
                if self._stderr_sink is not None:
                    self._stderr_sink(raw.decode(errors="replace").rstrip("\r\n"))
        except asyncio.CancelledError:
            pass

    async def send(self, line: str) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("transport not started")
        self._proc.stdin.write(line.encode() + b"\n")
        await self._proc.stdin.drain()

    async def receive_lines(self) -> AsyncIterator[str]:
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("transport not started")
        async for raw in self._proc.stdout:
            text = raw.decode(errors="replace").rstrip("\r\n")
            if text:
                yield text

    async def aclose(self, timeout: float = 5.0) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin is not None and not self._proc.stdin.is_closing():
                self._proc.stdin.close()
        except (RuntimeError, ConnectionError):
            pass
        if self._stderr_task is not None:
            self._stderr_task.cancel()
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=timeout)
        except TimeoutError:
            self._proc.kill()
            await self._proc.wait()

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode if self._proc else None
