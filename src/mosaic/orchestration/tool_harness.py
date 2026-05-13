"""ToolHarness — discovers, validates, executes tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    import pydantic  # noqa: F401
    HAVE_PYDANTIC = True
except ImportError:
    HAVE_PYDANTIC = False


@dataclass
class ToolSpec:
    """Metadata describing a callable tool."""
    name: str
    description: str
    func: Callable
    parameters: dict | None = None
    return_type: str | None = None

    def validate_args(self, args: dict) -> tuple[bool, str]:
        if self.parameters is None:
            return True, ""
        required = set(self.parameters.get("required", []))
        provided = set(args.keys())
        missing = required - provided
        if missing:
            return False, f"Missing args: {', '.join(missing)}"
        # Type validation could be added here
        return True, ""

    def call(self, **kwargs) -> Any:
        ok, reason = self.validate_args(kwargs)
        if not ok:
            raise ValueError(f"Tool argument error: {reason}")
        return self.func(**kwargs)


class ToolHarness:
    """Registry of tools + safe execution."""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._blocklist: set[str] = set()

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_spec(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def block(self, name: str) -> None:
        self._blocklist.add(name)

    def call(self, name: str, **kwargs) -> Any:
        if name in self._blocklist:
            raise RuntimeError(f"Tool {name} is blocked")
        spec = self._tools.get(name)
        if spec is None:
            raise RuntimeError(f"Unknown tool: {name}")
        return spec.call(**kwargs)


__all__ = [
    "ToolHarness",
    "ToolSpec",
]
