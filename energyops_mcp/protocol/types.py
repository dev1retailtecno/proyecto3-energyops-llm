"""Lightweight MCP data types: tools and tool-call results.

Deliberately not a full schema of the MCP spec -- only what the client and
our own server actually need (tool discovery + tool invocation results).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Tool:
        return cls(
            name=d["name"],
            description=d.get("description"),
            input_schema=d.get("inputSchema") or {"type": "object"},
            output_schema=d.get("outputSchema"),
            raw=d,
        )

    def to_wire(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "inputSchema": self.input_schema}
        if self.description is not None:
            d["description"] = self.description
        if self.output_schema is not None:
            d["outputSchema"] = self.output_schema
        return d

    def to_anthropic_tool(self) -> dict[str, Any]:
        """Render as an Anthropic Messages API tool definition."""
        return {
            "name": self.name,
            "description": self.description or "",
            "input_schema": self.input_schema,
        }


def text_content(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


@dataclass(frozen=True)
class CallToolResult:
    content: list[dict[str, Any]]
    is_error: bool = False
    structured_content: dict[str, Any] | None = None

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> CallToolResult:
        return cls(
            content=d.get("content", []),
            is_error=bool(d.get("isError", False)),
            structured_content=d.get("structuredContent"),
        )

    def to_wire(self) -> dict[str, Any]:
        d: dict[str, Any] = {"content": self.content, "isError": self.is_error}
        if self.structured_content is not None:
            d["structuredContent"] = self.structured_content
        return d

    def text(self) -> str:
        """Concatenate all text content blocks -- what most callers actually want."""
        return "\n".join(b.get("text", "") for b in self.content if b.get("type") == "text")

    @classmethod
    def ok(cls, text: str, structured: dict[str, Any] | None = None) -> CallToolResult:
        return cls(content=[text_content(text)], is_error=False, structured_content=structured)

    @classmethod
    def error(cls, text: str) -> CallToolResult:
        return cls(content=[text_content(text)], is_error=True)
