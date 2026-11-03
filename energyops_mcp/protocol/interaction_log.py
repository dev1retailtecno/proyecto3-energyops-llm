"""JSONL logger for every MCP message exchanged with any server.

Records the full JSON-RPC envelope plus timing/session metadata so the
terminal UI can filter and expand traffic per requirement #3 (mantener y
mostrar un log de interacciones). Never receives or writes API keys or
Authorization headers -- callers must not pass HTTP auth headers into
`payload`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Direction = Literal["out", "in"]


class InteractionLogger:
    def __init__(self, path: Path, session_id: str):
        self._path = Path(path)
        self._session_id = session_id
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def log(
        self,
        *,
        server: str,
        direction: Direction,
        payload: dict[str, Any],
        duration_ms: float | None = None,
        outcome: str | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": self._session_id,
            "server": server,
            "direction": direction,
            "method": payload.get("method"),
            "id": payload.get("id"),
            "message": payload,
            "duration_ms": duration_ms,
            "outcome": outcome,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
