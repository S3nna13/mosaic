"""SafetyGate + concrete implementations + GateEnforcer."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class SafetyGate(ABC):
    """Abstract safety check with veto power."""

    @abstractmethod
    def check(self, context: dict[str, Any]) -> tuple[bool, str | None]:
        """Return (allowed: True/False, reason if disallowed)."""


class UnsafeMemoryWriteGate(SafetyGate):
    """Reject memory writes containing PII or secrets."""

    PII_PATTERNS = (
        r"\\b\\d{3}-\\d{2}-\\d{4}\\b",  # SSN
        r"\\b[\\d]{10,}\\b",
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",  # email
        r"\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b",  # IPv4
    ]
)
    def check(self, context: dict[str, Any]) -> tuple[bool, str | None]:
        content = str(context.get("memory_content", ""))
        for pattern in self.PII_PATTERNS:
            if re.search(pattern, content):
                return False, "PII detected in memory write"
        return True, None


class InvalidToolSchemaGate(SafetyGate):
    """Ensure tool calls match declared schema."""

    def check(self, context: dict[str, Any]) -> tuple[bool, str | None]:
        tc = context.get("tool_call")
        if not tc:
            return True, None
        schema = context.get("tool_schema") or {}
        required = set(schema.get("required", []))
        provided = set(tc.get("parameters", {}).keys())
        missing = required - provided
        if missing:
            return False, f"Missing required tool parameters: {', '.join(missing)}"
        return True, None


class PrivateDataExtractionGate(SafetyGate):
    """Detect attempts to extract system prompts / private data."""

    INJECT_PATTERNS = [
        r"(?i)ignore (?:previous|above|system) instructions",
        r"(?i)reveal (?:your|the) (?:system|hidden) (?:prompt|instructions)",
        r"(?i)print your system prompt",
    ]
)
    def check(self, context: dict[str, Any]) -> tuple[bool, str | None]:
        prompt = str(context.get("prompt", ""))
        for pattern in self.INJECT_PATTERNS:
            if re.search(pattern, prompt):
                return False, "Prompt injection / data extraction attempt"
        return True, None


class GateEnforcer:
    """Runs all gates in order; aggregates violations."""

    def __init__(self, gates: list[SafetyGate]):
        self.gates = gates

    def enforce(self, context: dict[str, Any]) -> tuple[bool, list[str]]:
        violations: list[str] = []
        for gate in self.gates:
            passed, reason = gate.check(context)
            if not passed:
                violations.append(reason or "Gate blocked")
        return len(violations) == 0, violations


__all__ = [
    "GateEnforcer",
    "InvalidToolSchemaGate",
    "PrivateDataExtractionGate",
    "SafetyGate",
    "UnsafeMemoryWriteGate",
]
)